"""
CFE - Confluence Futures Engine: reference Python implementation.

This module mirrors the Pine Script v6 logic in pine/CFE_indicator.pine bar by bar.
All calculations are causal: the value produced for bar i uses only bars <= i
(higher-timeframe values use the previous *closed* HTF bar, identical to
request.security(..., expr[1], lookahead = barmerge.lookahead_on)).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from numba import njit

from . import indicators as ind


# --------------------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------------------
@dataclass
class Params:
    # trend
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 100
    ema_base: int = 200
    htf_list: tuple = ("15m", "1h", "4h")
    htf_weights: tuple = (1.0, 1.5, 2.0)
    local_weight: float = 1.0
    # structure / liquidity
    pivot_len: int = 5
    liq_slots: int = 10
    eq_tol_atr: float = 0.15
    fvg_min_atr: float = 0.25
    zone_tap_bars: int = 5
    sweep_recent_bars: int = 3
    div_active_bars: int = 10
    ob_search_bars: int = 50
    # volume
    rvol_len: int = 20
    pressure_len: int = 10
    use_real_delta: bool = False      # Python only: taker-buy based delta (not available in Pine)
    # momentum
    rsi_len: int = 14
    # volatility
    atr_len: int = 14
    atr_rank_len: int = 500
    vol_rank_lo: float = 20.0
    vol_rank_hi: float = 90.0
    vol_rank_max: float = 98.0        # hard filter: above -> no trade
    # triggers
    use_sweep: bool = True
    use_break: bool = True
    use_pullback: bool = True
    break_body_frac: float = 0.5
    break_range_atr: float = 0.8
    # risk model
    sl_lookback: int = 5
    sl_buffer_atr: float = 0.2
    sl_min_atr: float = 0.75
    sl_max_atr: float = 3.0
    tp1_r: float = 1.0
    tp2_r: float = 2.0
    tp3_r: float = 3.0
    tp_mode: int = 0                  # 0 fixed R, 1 liquidity adaptive
    min_rr: float = 2.0               # TP2 must be >= min_rr (adaptive mode)
    room_min_r: float = 1.0           # opposing liquidity must be at least this many R away
    # costs (per side, in %)
    fee_taker: float = 0.05
    fee_maker: float = 0.02
    slippage: float = 0.02
    tp_as_maker: bool = True
    cost_mult: float = 4.0            # stop distance must be >= cost_mult * round-trip cost
    # scoring
    w_trend: float = 25.0
    w_struct: float = 15.0
    w_volume: float = 15.0
    w_momentum: float = 15.0
    w_liquidity: float = 15.0
    w_volatility: float = 10.0
    w_room: float = 5.0
    min_score: float = 65.0
    htf_veto: float = -0.5            # if weighted HTF alignment (excluding chart TF) <= this -> veto
    # trade management
    frac_tp1: float = 1.0 / 3.0
    frac_tp2: float = 1.0 / 3.0
    be_after_tp1: bool = True
    lock_after_tp2: bool = True
    trail_atr: float = 0.0            # 0 = off; else chandelier trail after TP1
    exit_on_choch: bool = True
    reverse_on_opposite: bool = True
    max_bars: int = 0                 # 0 = off
    cooldown: int = 0

    def to_dict(self):
        return asdict(self)


TF_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
         "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}


# --------------------------------------------------------------------------------------
# Resampling / MTF (no look-ahead)
# --------------------------------------------------------------------------------------
def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    ms = TF_MS[tf]
    g = (df["open_time"] // ms) * ms
    agg = df.groupby(g).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                            close=("close", "last"), volume=("volume", "sum"),
                            quote_volume=("quote_volume", "sum"),
                            taker_buy_volume=("taker_buy_volume", "sum"))
    agg.index.name = "open_time"
    agg = agg.reset_index()
    agg["time"] = pd.to_datetime(agg["open_time"], unit="ms", utc=True)
    return agg


def trend_state(c: np.ndarray, p: Params) -> np.ndarray:
    """T in [-1,1]: EMA stack + price location. Identical to f_trendState() in Pine."""
    e1 = ind.ema(c, p.ema_fast)
    e2 = ind.ema(c, p.ema_mid)
    e3 = ind.ema(c, p.ema_slow)
    e4 = ind.ema(c, p.ema_base)
    return 0.25 * (np.sign(c - e2) + np.sign(e1 - e2) + np.sign(e2 - e3) + np.sign(e3 - e4))


def htf_state_aligned(df_chart: pd.DataFrame, df_base: pd.DataFrame, tf: str, p: Params) -> np.ndarray:
    """HTF trend state of the previous CLOSED HTF bar mapped onto chart bars.
    Equivalent to request.security(sym, tf, f()[1], lookahead=barmerge.lookahead_on)."""
    h = resample(df_base, tf)
    t = trend_state(h["close"].to_numpy(), p)
    t_prev = np.concatenate([[np.nan], t[:-1]])
    ms = TF_MS[tf]
    key = (df_chart["open_time"].to_numpy() // ms) * ms
    idx = np.searchsorted(h["open_time"].to_numpy(), key)
    idx = np.clip(idx, 0, len(h) - 1)
    out = t_prev[idx]
    # Guard: HTF bar must start at key (it always does for contiguous data)
    return out


# --------------------------------------------------------------------------------------
# Structure + liquidity state machine (identical to the Pine var-state logic)
# --------------------------------------------------------------------------------------
@njit(cache=True)
def structure_pass(o, h, l, c, atr, rsi, piv_len, liq_slots, eq_tol_atr, fvg_min_atr,
                   zone_tap_bars, div_active_bars, ob_search_bars):
    n = c.shape[0]
    ms = np.zeros(n, np.int8)
    bull_break = np.zeros(n, np.int8)    # 1 BOS, 2 CHoCH
    bear_break = np.zeros(n, np.int8)
    bull_sweep = np.zeros(n, np.bool_)
    bear_sweep = np.zeros(n, np.bool_)
    bull_tap = np.zeros(n, np.bool_)
    bear_tap = np.zeros(n, np.bool_)
    hhhl = np.zeros(n, np.int8)
    bull_div = np.zeros(n, np.bool_)
    bear_div = np.zeros(n, np.bool_)
    up_liq1 = np.full(n, np.nan)        # nearest opposing liquidity above close
    up_liq2 = np.full(n, np.nan)        # second nearest
    dn_liq1 = np.full(n, np.nan)
    dn_liq2 = np.full(n, np.nan)
    eqh = np.zeros(n, np.bool_)
    eql = np.zeros(n, np.bool_)
    last_ph_arr = np.full(n, np.nan)
    last_pl_arr = np.full(n, np.nan)
    brk_lvl_l = np.full(n, np.nan)      # level broken by a bullish break (old swing high)
    leg_ext_l = np.full(n, np.nan)      # lowest low of the impulse leg that produced the break
    brk_lvl_s = np.full(n, np.nan)
    leg_ext_s = np.full(n, np.nan)

    # liquidity pools: recent unswept pivot highs / lows
    ph_lv = np.full(liq_slots, np.nan)
    pl_lv = np.full(liq_slots, np.nan)
    # zones: bullish/bearish FVG + OB (top, bottom), up to 5 each
    NZ = 5
    bfvg_t = np.full(NZ, np.nan); bfvg_b = np.full(NZ, np.nan)
    sfvg_t = np.full(NZ, np.nan); sfvg_b = np.full(NZ, np.nan)
    bob_t = np.full(NZ, np.nan); bob_b = np.full(NZ, np.nan)
    sob_t = np.full(NZ, np.nan); sob_b = np.full(NZ, np.nan)

    last_ph = np.nan; prev_ph = np.nan; last_ph_bar = -1; ph_broken = True
    last_pl = np.nan; prev_pl = np.nan; last_pl_bar = -1; pl_broken = True
    last_ph_rsi = np.nan; last_pl_rsi = np.nan
    state = 0
    last_bull_tap = -100000; last_bear_tap = -100000
    last_bull_div = -100000; last_bear_div = -100000
    win = 2 * piv_len + 1

    for i in range(n):
        a = atr[i]
        # ---------------- pivots (confirmed piv_len bars later) ----------------
        if i >= win - 1 and not np.isnan(a):
            p = i - piv_len
            mx = h[p]; mn = l[p]
            isph = True; ispl = True
            for j in range(i - win + 1, i + 1):
                if h[j] > mx:
                    isph = False
                if l[j] < mn:
                    ispl = False
            if isph:
                prev_ph = last_ph
                last_ph = h[p]; last_ph_bar = p; ph_broken = False
                if not np.isnan(prev_ph) and abs(last_ph - prev_ph) <= eq_tol_atr * a:
                    eqh[i] = True
                # bearish regular divergence: HH in price, LH in RSI
                if not np.isnan(prev_ph) and last_ph > prev_ph and not np.isnan(last_ph_rsi) and rsi[p] < last_ph_rsi:
                    last_bear_div = i
                last_ph_rsi = rsi[p]
                # push into liquidity pool (replace oldest / NaN)
                k = 0
                for s in range(liq_slots):
                    if np.isnan(ph_lv[s]):
                        k = s
                        break
                    k = -1
                if k == -1:
                    for s in range(liq_slots - 1):
                        ph_lv[s] = ph_lv[s + 1]
                    k = liq_slots - 1
                ph_lv[k] = last_ph
            if ispl:
                prev_pl = last_pl
                last_pl = l[p]; last_pl_bar = p; pl_broken = False
                if not np.isnan(prev_pl) and abs(last_pl - prev_pl) <= eq_tol_atr * a:
                    eql[i] = True
                if not np.isnan(prev_pl) and last_pl < prev_pl and not np.isnan(last_pl_rsi) and rsi[p] > last_pl_rsi:
                    last_bull_div = i
                last_pl_rsi = rsi[p]
                k = 0
                for s in range(liq_slots):
                    if np.isnan(pl_lv[s]):
                        k = s
                        break
                    k = -1
                if k == -1:
                    for s in range(liq_slots - 1):
                        pl_lv[s] = pl_lv[s + 1]
                    k = liq_slots - 1
                pl_lv[k] = last_pl

        # HH/HL sequence
        if not np.isnan(prev_ph) and not np.isnan(prev_pl):
            if last_ph > prev_ph and last_pl > prev_pl:
                hhhl[i] = 1
            elif last_ph < prev_ph and last_pl < prev_pl:
                hhhl[i] = -1

        # ---------------- sweeps (wick through, close back) ----------------
        for s in range(liq_slots):
            lv = pl_lv[s]
            if not np.isnan(lv) and l[i] < lv:
                if c[i] > lv:
                    bull_sweep[i] = True
                pl_lv[s] = np.nan     # liquidity consumed (swept or broken)
            lv = ph_lv[s]
            if not np.isnan(lv) and h[i] > lv:
                if c[i] < lv:
                    bear_sweep[i] = True
                ph_lv[s] = np.nan

        # ---------------- structure breaks on close ----------------
        if not ph_broken and not np.isnan(last_ph) and c[i] > last_ph:
            ph_broken = True
            brk_lvl_l[i] = last_ph
            mn = l[i]
            for j in range(max(last_pl_bar, i - ob_search_bars, 0), i):
                if l[j] < mn:
                    mn = l[j]
            leg_ext_l[i] = mn
            bull_break[i] = 2 if state == -1 else 1
            state = 1
            # order block: last bearish candle in the leg before the break
            lo = max(last_pl_bar, i - ob_search_bars, 0)
            for j in range(i - 1, lo - 1, -1):
                if c[j] < o[j]:
                    for s in range(NZ - 1):
                        bob_t[s] = bob_t[s + 1]; bob_b[s] = bob_b[s + 1]
                    bob_t[NZ - 1] = h[j]; bob_b[NZ - 1] = l[j]
                    break
        if not pl_broken and not np.isnan(last_pl) and c[i] < last_pl:
            pl_broken = True
            brk_lvl_s[i] = last_pl
            mx = h[i]
            for j in range(max(last_ph_bar, i - ob_search_bars, 0), i):
                if h[j] > mx:
                    mx = h[j]
            leg_ext_s[i] = mx
            bear_break[i] = 2 if state == 1 else 1
            state = -1
            lo = max(last_ph_bar, i - ob_search_bars, 0)
            for j in range(i - 1, lo - 1, -1):
                if c[j] > o[j]:
                    for s in range(NZ - 1):
                        sob_t[s] = sob_t[s + 1]; sob_b[s] = sob_b[s + 1]
                    sob_t[NZ - 1] = h[j]; sob_b[NZ - 1] = l[j]
                    break
        ms[i] = state

        # ---------------- fair value gaps ----------------
        if i >= 2 and not np.isnan(a):
            if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= fvg_min_atr * a:
                for s in range(NZ - 1):
                    bfvg_t[s] = bfvg_t[s + 1]; bfvg_b[s] = bfvg_b[s + 1]
                bfvg_t[NZ - 1] = l[i]; bfvg_b[NZ - 1] = h[i - 2]
            if h[i] < l[i - 2] and (l[i - 2] - h[i]) >= fvg_min_atr * a:
                for s in range(NZ - 1):
                    sfvg_t[s] = sfvg_t[s + 1]; sfvg_b[s] = sfvg_b[s + 1]
                sfvg_t[NZ - 1] = l[i - 2]; sfvg_b[NZ - 1] = h[i]

        # ---------------- zone taps + invalidation ----------------
        for s in range(NZ):
            # bullish zones: tap = low into zone, close not below bottom; invalid if close < bottom
            for zz in range(2):
                if zz == 0:
                    t = bfvg_t[s]; b = bfvg_b[s]
                else:
                    t = bob_t[s]; b = bob_b[s]
                if not np.isnan(t):
                    if c[i] < b:
                        if zz == 0:
                            bfvg_t[s] = np.nan; bfvg_b[s] = np.nan
                        else:
                            bob_t[s] = np.nan; bob_b[s] = np.nan
                    elif l[i] <= t:
                        last_bull_tap = i
            for zz in range(2):
                if zz == 0:
                    t = sfvg_t[s]; b = sfvg_b[s]
                else:
                    t = sob_t[s]; b = sob_b[s]
                if not np.isnan(t):
                    if c[i] > t:
                        if zz == 0:
                            sfvg_t[s] = np.nan; sfvg_b[s] = np.nan
                        else:
                            sob_t[s] = np.nan; sob_b[s] = np.nan
                    elif h[i] >= b:
                        last_bear_tap = i
        bull_tap[i] = (i - last_bull_tap) < zone_tap_bars
        bear_tap[i] = (i - last_bear_tap) < zone_tap_bars
        bull_div[i] = (i - last_bull_div) < div_active_bars
        bear_div[i] = (i - last_bear_div) < div_active_bars

        # ---------------- opposing liquidity (targets / room) ----------------
        u1 = np.inf; u2 = np.inf; d1 = -np.inf; d2 = -np.inf
        for s in range(liq_slots):
            lv = ph_lv[s]
            if not np.isnan(lv) and lv > c[i]:
                if lv < u1:
                    u2 = u1; u1 = lv
                elif lv < u2:
                    u2 = lv
            lv = pl_lv[s]
            if not np.isnan(lv) and lv < c[i]:
                if lv > d1:
                    d2 = d1; d1 = lv
                elif lv > d2:
                    d2 = lv
        for s in range(NZ):
            for zz in range(2):
                b = sfvg_b[s] if zz == 0 else sob_b[s]
                if not np.isnan(b) and b > c[i]:
                    if b < u1:
                        u2 = u1; u1 = b
                    elif b < u2:
                        u2 = b
                t = bfvg_t[s] if zz == 0 else bob_t[s]
                if not np.isnan(t) and t < c[i]:
                    if t > d1:
                        d2 = d1; d1 = t
                    elif t > d2:
                        d2 = t
        up_liq1[i] = u1 if u1 < np.inf else np.nan
        up_liq2[i] = u2 if u2 < np.inf else np.nan
        dn_liq1[i] = d1 if d1 > -np.inf else np.nan
        dn_liq2[i] = d2 if d2 > -np.inf else np.nan
        last_ph_arr[i] = last_ph
        last_pl_arr[i] = last_pl

    return (ms, bull_break, bear_break, bull_sweep, bear_sweep, bull_tap, bear_tap, hhhl,
            bull_div, bear_div, up_liq1, up_liq2, dn_liq1, dn_liq2, eqh, eql, last_ph_arr, last_pl_arr,
            brk_lvl_l, leg_ext_l, brk_lvl_s, leg_ext_s)


def _clamp(x, lo=0.0, hi=1.0):
    return np.minimum(np.maximum(x, lo), hi)


def bars_since_true(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape[0], 10**9, dtype=np.int64)
    last = -10**9
    for i in range(x.shape[0]):
        if x[i]:
            last = i
        out[i] = i - last
    return out


# --------------------------------------------------------------------------------------
# Feature + signal computation
# --------------------------------------------------------------------------------------
def compute(df: pd.DataFrame, p: Params, base_df: pd.DataFrame | None = None, chart_tf: str = "5m") -> dict:
    """Compute all layers, scores, triggers and risk levels for a chart dataframe.
    base_df: finest available data used to build HTF bars (defaults to df)."""
    if base_df is None:
        base_df = df
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    n = len(c)
    R = {}

    # ---- A. trend ----
    t_local = trend_state(c, p)
    e_fast = ind.ema(c, p.ema_fast)
    e_mid = ind.ema(c, p.ema_mid)
    htf = {}
    chart_ms = TF_MS[chart_tf]
    wsum = p.local_weight
    align_num = p.local_weight * t_local
    h_num = np.zeros(n); h_w = 0.0
    for tf, w in zip(p.htf_list, p.htf_weights):
        if TF_MS[tf] <= chart_ms:
            continue
        s = htf_state_aligned(df, base_df, tf, p)
        htf[tf] = s
        s0 = np.nan_to_num(s, nan=0.0)
        align_num = align_num + w * s0
        wsum += w
        h_num = h_num + w * s0
        h_w += w
    align = align_num / wsum                     # in [-1, 1], positive = bullish
    htf_align = h_num / h_w if h_w > 0 else np.zeros(n)

    # ---- E. volatility ----
    atr = ind.atr(h, l, c, p.atr_len)
    atr_pct = atr / c
    atr_rank = ind.percentrank(atr_pct, p.atr_rank_len)

    # ---- B. volume ----
    vavg = ind.sma(v, p.rvol_len)
    vprev = np.concatenate([[np.nan], vavg[:-1]])
    rvol = np.where(vprev > 0, v / np.where(vprev > 0, vprev, 1.0), np.nan)
    rng = h - l
    clv = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    est_delta = v * (2.0 * clv - 1.0)
    if p.use_real_delta and "taker_buy_volume" in df:
        delta = 2.0 * df["taker_buy_volume"].to_numpy(float) - v
    else:
        delta = est_delta
    vsum = ind.rolling_sum(v, p.pressure_len)
    pressure = np.where(vsum > 0, ind.rolling_sum(delta, p.pressure_len) / np.where(vsum > 0, vsum, 1.0), 0.0)

    # ---- C. momentum ----
    rsi = ind.rsi(c, p.rsi_len)
    hist = ind.macd_hist(c)
    hist_prev = np.concatenate([[np.nan], hist[:-1]])

    # ---- D. structure & liquidity ----
    (ms, bull_break, bear_break, bull_sweep, bear_sweep, bull_tap, bear_tap, hhhl, bull_div, bear_div,
     up1, up2, dn1, dn2, eqh, eql, last_ph, last_pl, brk_l, leg_l, brk_s, leg_s) = structure_pass(
        o, h, l, c, atr, np.nan_to_num(rsi, nan=50.0), p.pivot_len, p.liq_slots, p.eq_tol_atr, p.fvg_min_atr,
        p.zone_tap_bars, p.div_active_bars, p.ob_search_bars)
    bs_bull_sweep = bars_since_true(bull_sweep)
    bs_bear_sweep = bars_since_true(bear_sweep)

    # ---- triggers ----
    body = np.abs(c - o)
    ms_prev = np.concatenate([[0], ms[:-1]])
    low_prev = np.concatenate([[np.nan], l[:-1]]); high_prev = np.concatenate([[np.nan], h[:-1]])
    pulled_long = bars_since_true(l <= e_fast) < p.zone_tap_bars
    pulled_short = bars_since_true(h >= e_fast) < p.zone_tap_bars

    trg_sw_l = bull_sweep & (clv >= 0.5)
    trg_sw_s = bear_sweep & (clv <= 0.5)
    disp = (body >= p.break_body_frac * rng) & (rng >= p.break_range_atr * atr)
    trg_br_l = (bull_break > 0) & disp & (c > o)
    trg_br_s = (bear_break > 0) & disp & (c < o)
    trg_pb_l = (ms_prev == 1) & (pulled_long | bull_tap) & (c > o) & (c > high_prev) & (c > e_fast) & (bull_break == 0)
    trg_pb_s = (ms_prev == -1) & (pulled_short | bear_tap) & (c < o) & (c < low_prev) & (c < e_fast) & (bear_break == 0)
    trig_l = np.zeros(n, np.int8); trig_s = np.zeros(n, np.int8)  # 1 sweep, 2 break, 3 pullback
    if p.use_pullback:
        trig_l[trg_pb_l] = 3; trig_s[trg_pb_s] = 3
    if p.use_break:
        trig_l[trg_br_l] = 2; trig_s[trg_br_s] = 2
    if p.use_sweep:
        trig_l[trg_sw_l] = 1; trig_s[trg_sw_s] = 1

    # ---- risk model ----
    lowest = ind.rolling_min(l, p.sl_lookback)
    highest = ind.rolling_max(h, p.sl_lookback)
    inval_l = lowest; inval_s = highest
    sl_l = inval_l - p.sl_buffer_atr * atr
    sl_s = inval_s + p.sl_buffer_atr * atr
    dist_l = c - sl_l; dist_s = sl_s - c
    dist_l = np.maximum(dist_l, p.sl_min_atr * atr); dist_s = np.maximum(dist_s, p.sl_min_atr * atr)
    sl_l = c - dist_l; sl_s = c + dist_s
    rt_cost = 2.0 * (p.fee_taker + p.slippage) / 100.0
    ok_dist_l = (dist_l <= p.sl_max_atr * atr) & (dist_l / c >= p.cost_mult * rt_cost)
    ok_dist_s = (dist_s <= p.sl_max_atr * atr) & (dist_s / c >= p.cost_mult * rt_cost)

    room_l = (up1 - c) / dist_l       # NaN if no opposing liquidity known
    room_s = (c - dn1) / dist_s

    # TP levels
    tp1_l = c + p.tp1_r * dist_l; tp2_l = c + p.tp2_r * dist_l; tp3_l = c + p.tp3_r * dist_l
    tp1_s = c - p.tp1_r * dist_s; tp2_s = c - p.tp2_r * dist_s; tp3_s = c - p.tp3_r * dist_s
    if p.tp_mode == 1:
        buf = 0.1 * atr
        # snap TP2 to the nearest opposing liquidity that is >= min_rr and <= 5R away (front-run by 0.1 ATR)
        cand2_l = np.where(~np.isnan(up1) & ((up1 - buf - c) >= p.min_rr * dist_l) & ((up1 - buf - c) <= 5 * dist_l), up1 - buf,
                   np.where(~np.isnan(up2) & ((up2 - buf - c) >= p.min_rr * dist_l) & ((up2 - buf - c) <= 5 * dist_l), up2 - buf, np.nan))
        tp2_l = np.where(np.isnan(cand2_l), tp2_l, cand2_l)
        tp3_l = np.maximum(tp3_l, tp2_l + 1.0 * dist_l)
        cand2_s = np.where(~np.isnan(dn1) & ((c - dn1 - buf) >= p.min_rr * dist_s) & ((c - dn1 - buf) <= 5 * dist_s), dn1 + buf,
                   np.where(~np.isnan(dn2) & ((c - dn2 - buf) >= p.min_rr * dist_s) & ((c - dn2 - buf) <= 5 * dist_s), dn2 + buf, np.nan))
        tp2_s = np.where(np.isnan(cand2_s), tp2_s, cand2_s)
        tp3_s = np.minimum(tp3_s, tp2_s - 1.0 * dist_s)

    # ---- scoring ----
    def score_dir(d):
        trend = _clamp((d * align + 1.0) / 2.0)
        msd = ms * d
        s1 = np.where(msd > 0, 1.0, np.where(msd == 0, 0.5, 0.0))
        hd = hhhl * d
        s2 = np.where(hd > 0, 1.0, np.where(hd == 0, 0.5, 0.0))
        struct = 0.6 * s1 + 0.4 * s2
        vol = 0.5 * _clamp(np.nan_to_num(rvol, nan=0.0) - 1.0) + 0.5 * _clamp(0.5 + 2.5 * d * np.nan_to_num(pressure))
        m1 = 0.5 * (d * hist > 0) + 0.5 * (d * (hist - hist_prev) > 0)
        rd = rsi if d == 1 else 100.0 - rsi
        m2 = np.where((rd >= 50) & (rd <= 70), 1.0, np.where((rd >= 40) & (rd < 50), 0.6,
             np.where((rd > 70) & (rd <= 80), 0.3, np.where(rd > 80, 0.0, 0.2))))
        m3 = (bull_div if d == 1 else bear_div).astype(float)
        mom = 0.45 * m1 + 0.35 * m2 + 0.2 * m3
        bs = bs_bull_sweep if d == 1 else bs_bear_sweep
        tap = bull_tap if d == 1 else bear_tap
        liq = 0.55 * (bs < p.sweep_recent_bars) + 0.45 * tap
        r = np.nan_to_num(atr_rank, nan=50.0)
        vola = np.where((r >= p.vol_rank_lo) & (r <= p.vol_rank_hi), 1.0,
                np.where((r >= p.vol_rank_lo / 2) & (r <= p.vol_rank_max), 0.5, 0.0))
        room = room_l if d == 1 else room_s
        rr = np.where(np.isnan(room), 1.0, _clamp((room - 1.0) / 2.0))
        comps = dict(trend=trend, struct=struct, volume=vol, momentum=mom, liquidity=liq, volatility=vola, room=rr)
        score = (p.w_trend * trend + p.w_struct * struct + p.w_volume * vol + p.w_momentum * mom +
                 p.w_liquidity * liq + p.w_volatility * vola + p.w_room * rr)
        return score, comps

    score_l, comp_l = score_dir(1)
    score_s, comp_s = score_dir(-1)

    # ---- hard filters ----
    r = np.nan_to_num(atr_rank, nan=100.0)
    vol_ok = r <= p.vol_rank_max
    veto_l = htf_align <= p.htf_veto
    veto_s = -htf_align <= p.htf_veto
    room_ok_l = np.isnan(room_l) | (room_l >= p.room_min_r)
    room_ok_s = np.isnan(room_s) | (room_s >= p.room_min_r)
    warm = np.arange(n) >= max(p.ema_base, p.atr_rank_len) + 5

    cand_l = (trig_l > 0) & ok_dist_l & vol_ok & ~veto_l & room_ok_l & warm
    cand_s = (trig_s > 0) & ok_dist_s & vol_ok & ~veto_s & room_ok_s & warm
    # never both directions on the same bar: keep the stronger by >= 10 points, else none
    both = cand_l & cand_s
    keep_l = ~both | (score_l >= score_s + 10)
    keep_s = ~both | (score_s >= score_l + 10)
    cand_l &= keep_l; cand_s &= keep_s

    sig_l = cand_l & (score_l >= p.min_score)
    sig_s = cand_s & (score_s >= p.min_score)

    R.update(dict(o=o, h=h, l=l, c=c, v=v, atr=atr, atr_rank=atr_rank, rvol=rvol, pressure=pressure,
                  est_delta=est_delta, rsi=rsi, hist=hist, ms=ms, bull_break=bull_break, bear_break=bear_break,
                  bull_sweep=bull_sweep, bear_sweep=bear_sweep, align=align, htf_align=htf_align, t_local=t_local,
                  trig_l=trig_l, trig_s=trig_s, score_l=score_l, score_s=score_s, comp_l=comp_l, comp_s=comp_s,
                  cand_l=cand_l, cand_s=cand_s, sig_l=sig_l, sig_s=sig_s,
                  sl_l=sl_l, sl_s=sl_s, tp1_l=tp1_l, tp2_l=tp2_l, tp3_l=tp3_l, tp1_s=tp1_s, tp2_s=tp2_s, tp3_s=tp3_s,
                  inval_l=inval_l, inval_s=inval_s, room_l=room_l, room_s=room_s, htf=htf,
                  open_time=df["open_time"].to_numpy(np.int64), eqh=eqh, eql=eql,
                  brk_l=brk_l, leg_l=leg_l, brk_s=brk_s, leg_s=leg_s, e_fast=e_fast, e_mid=e_mid,
                  up1=up1, up2=up2, dn1=dn1, dn2=dn2, hhhl=hhhl, bull_tap=bull_tap, bear_tap=bear_tap,
                  bull_div=bull_div, bear_div=bear_div, clv=clv))
    return R
