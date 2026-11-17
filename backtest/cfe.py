"""
CFE v2 - setup engine (reference implementation of pine/CFE_indicator.pine).

Setup (long; short is mirrored):
  1. Context   : weighted HTF trend alignment (15m/1h/4h EMA-stack state of the previous CLOSED
                 HTF bar) >= htf_min.
  2. Trigger   : confirmed bullish structure break (close > last unbroken swing high, BOS or CHoCH)
                 with displacement (body >= 50% of range and range >= 0.8 ATR).
  3. Plan      : entry = broken level (+offset*ATR) as a resting LIMIT order (or market at close),
                 SL = impulse-leg low - 0.2 ATR, TP1/2/3 = 1/2/3 R (or liquidity-adaptive TP2/TP3).
  4. Filters   : stop distance in [min,max] ATR, stop >= cost_mult * round-trip cost, extreme
                 volatility filter, room to the nearest opposing liquidity.
  5. Score     : 0-100 from calibrated feature weights (see calibrate.py), shown with the setup;
                 a setup becomes a SIGNAL only when score >= min_score.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

from . import indicators as ind
from .engine import TF_MS, resample, trend_state, htf_state_aligned, structure_pass, bars_since_true


@dataclass
class P2:
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 100
    ema_base: int = 200
    htf_list: tuple = ("15m", "1h", "4h")
    htf_weights: tuple = (1.0, 1.5, 2.0)
    htf_min: float = 0.5
    pivot_len: int = 5
    liq_slots: int = 10
    eq_tol_atr: float = 0.15
    fvg_min_atr: float = 0.25
    zone_tap_bars: int = 5
    div_active_bars: int = 10
    ob_search_bars: int = 50
    rvol_len: int = 20
    pressure_len: int = 10
    rsi_len: int = 14
    atr_len: int = 14
    atr_rank_len: int = 500
    vol_rank_max: float = 99.0
    # trigger
    disp_body: float = 0.5
    disp_range_atr: float = 0.8
    allow_choch: bool = True
    # plan
    entry_mode: int = 1            # 0 market at close, 1 limit retest of the broken level
    entry_offset_atr: float = 0.0  # limit placed this many ATR beyond the level toward price
    valid_bars: int = 12
    sl_buffer_atr: float = 0.2
    sl_min_atr: float = 0.5
    sl_max_atr: float = 6.0
    tp1_r: float = 1.0
    tp2_r: float = 2.0
    tp3_r: float = 3.0
    tp_mode: int = 0               # 0 fixed R, 1 liquidity adaptive
    min_rr: float = 2.0
    room_min_r: float = 0.0
    # costs (% per side)
    fee_taker: float = 0.05
    fee_maker: float = 0.02
    slippage: float = 0.02
    cost_mult: float = 4.0
    # score
    min_score: float = 0.0
    weights: dict = field(default_factory=dict)
    # management
    frac_tp1: float = 1.0 / 3.0
    frac_tp2: float = 1.0 / 3.0
    be_after_tp1: bool = True
    lock_after_tp2: bool = True
    trail_atr: float = 0.0
    exit_on_opposite: bool = False
    max_bars: int = 0
    session_filter: bool = False
    lowvol_filter: bool = False
    session_start_utc: int = 13
    session_end_utc: int = 24

    def to_dict(self):
        return asdict(self)


# Feature names used by the score (direction-adjusted, all known at the setup bar's close)
FEATURES = ["htf_align", "t_local", "disp_body", "disp_range", "leg_atr", "risk_atr", "atr_rank",
            "rvol", "pressure", "rsi_d", "macd_d", "room_r", "sweep_recent", "fvg_new", "choch", "hhhl_d"]


def _clamp(x, lo=0.0, hi=1.0):
    return np.minimum(np.maximum(x, lo), hi)


def score_from_features(F: dict, weights: dict) -> np.ndarray:
    """Score 0-100 = 100 * sum_k w_k * s_k(feature_k) / sum_k w_k, where each s_k is a fixed,
    monotone transform to [0,1] (same transforms in Pine). Weights come from calibration."""
    S = score_components(F)
    num = np.zeros_like(S["trend"])
    den = 0.0
    for k, w in weights.items():
        if w <= 0:
            continue
        num = num + w * S[k]
        den += w
    return 100.0 * num / den if den > 0 else np.full_like(num, 50.0)


def score_components(F: dict) -> dict:
    """Seven user-facing layers, each in [0,1]."""
    trend = _clamp((F["htf_align"] + 1.0) / 2.0) * 0.7 + _clamp((F["t_local"] + 1.0) / 2.0) * 0.3
    struct = 0.5 * F["disp_body"] + 0.25 * _clamp((F["disp_range"] - 0.8) / 1.7) + 0.25 * _clamp((F["hhhl_d"] + 1.0) / 2.0)
    volume = 0.5 * _clamp((F["rvol"] - 1.0) / 2.0) + 0.5 * _clamp(0.5 + 2.5 * F["pressure"])
    # momentum: reward "not overextended" (rsi_d in 50..65) and macd agreement
    rd = F["rsi_d"]
    m_rsi = np.where(rd < 50, _clamp((rd - 35) / 15), np.where(rd <= 65, 1.0, _clamp(1.0 - (rd - 65) / 20)))
    momentum = 0.6 * m_rsi + 0.4 * (F["macd_d"] > 0)
    liquidity = 0.5 * F["sweep_recent"] + 0.5 * F["fvg_new"]
    volatility = np.where(F["atr_rank"] > 97, 0.2, _clamp(F["atr_rank"] / 60.0))
    room = np.where(np.isnan(F["room_r"]), 1.0, _clamp((F["room_r"] - 1.0) / 2.0))
    return dict(trend=trend, struct=struct, volume=volume, momentum=momentum, liquidity=liquidity,
                volatility=volatility, room=room)


# Evidence-based weights (design period 2022-01..2023-06): only the trend layer showed out-of-time
# predictive value, so it dominates. See docs/03_validation_report.md.
DEFAULT_WEIGHTS = dict(trend=45, struct=15, volume=10, momentum=10, liquidity=10, volatility=10, room=0)


def lowvol_regime(df_chart: pd.DataFrame, base_df: pd.DataFrame) -> np.ndarray:
    """True when the 30-day daily-return volatility (population stdev) of the previous CLOSED daily
    bar is below its 365-day median. Pine: request.security(sym, "1D", f_lowVol()[1], lookahead_on)."""
    d = resample(base_df, "1d")
    lr = np.log(d["close"] / d["close"].shift(1))
    vol = lr.rolling(30).std(ddof=0)
    med = vol.rolling(365).median()
    flag = (vol < med).to_numpy()
    flag_prev = np.concatenate([[False], flag[:-1]])
    key = (df_chart["open_time"].to_numpy() // TF_MS["1d"]) * TF_MS["1d"]
    idx = np.clip(np.searchsorted(d["open_time"].to_numpy(), key), 0, len(d) - 1)
    return flag_prev[idx]


def compute(df: pd.DataFrame, p: P2, base_df: pd.DataFrame | None = None, chart_tf: str = "5m") -> dict:
    if base_df is None:
        base_df = df
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    n = len(c)
    ot = df["open_time"].to_numpy(np.int64)

    # trend / MTF
    t_local = trend_state(c, p)
    chart_ms = TF_MS[chart_tf]
    h_num = np.zeros(n); h_w = 0.0
    for tf, w in zip(p.htf_list, p.htf_weights):
        if TF_MS[tf] <= chart_ms:
            continue
        s = htf_state_aligned(df, base_df, tf, p)
        h_num += w * np.nan_to_num(s, nan=0.0)
        h_w += w
    htf_align = h_num / h_w if h_w > 0 else np.zeros(n)

    atr = ind.atr(h, l, c, p.atr_len)
    atr_rank = ind.percentrank(atr / c, p.atr_rank_len)
    vavg = ind.sma(v, p.rvol_len)
    vprev = np.concatenate([[np.nan], vavg[:-1]])
    rvol = np.where(vprev > 0, v / np.where(vprev > 0, vprev, 1.0), 1.0)
    rng = h - l
    clv = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    vsum = ind.rolling_sum(v, p.pressure_len)
    pressure = np.where(vsum > 0, ind.rolling_sum(v * (2 * clv - 1), p.pressure_len) / np.where(vsum > 0, vsum, 1.0), 0.0)
    rsi = ind.rsi(c, p.rsi_len)
    hist = ind.macd_hist(c)

    (ms, bull_break, bear_break, bull_sweep, bear_sweep, bull_tap, bear_tap, hhhl, bull_div, bear_div,
     up1, up2, dn1, dn2, eqh, eql, last_ph, last_pl, brk_l, leg_l, brk_s, leg_s) = structure_pass(
        o, h, l, c, atr, np.nan_to_num(rsi, nan=50.0), p.pivot_len, p.liq_slots, p.eq_tol_atr, p.fvg_min_atr,
        p.zone_tap_bars, p.div_active_bars, p.ob_search_bars)

    body = np.abs(c - o)
    body_frac = np.where(rng > 0, body / np.where(rng > 0, rng, 1.0), 0.0)
    range_atr = rng / atr
    disp = (body_frac >= p.disp_body) & (range_atr >= p.disp_range_atr)
    # FVG created by the displacement (3-bar gap ending on this bar)
    h2 = np.concatenate([[np.nan, np.nan], h[:-2]]); l2 = np.concatenate([[np.nan, np.nan], l[:-2]])
    fvg_bull_new = (l > h2) & ((l - h2) >= p.fvg_min_atr * atr)
    fvg_bear_new = (h < l2) & ((l2 - h) >= p.fvg_min_atr * atr)
    bs_bull_sw = bars_since_true(bull_sweep)
    bs_bear_sw = bars_since_true(bear_sweep)
    hour = ((ot // 3_600_000) % 24).astype(np.int64)
    # session check uses the hour in which the signal bar CLOSES
    hour_close = (((ot + chart_ms - 1) // 3_600_000) % 24).astype(np.int64)
    in_session = (hour_close >= p.session_start_utc) & (hour_close < p.session_end_utc)

    warm = np.arange(n) >= max(p.ema_base, p.atr_rank_len) + 5
    lowvol = lowvol_regime(df, base_df)
    rt_cost = 2.0 * (p.fee_taker + p.slippage) / 100.0
    out = dict(o=o, h=h, l=l, c=c, v=v, atr=atr, atr_rank=atr_rank, rvol=rvol, pressure=pressure, rsi=rsi,
               hist=hist, ms=ms, bull_break=bull_break, bear_break=bear_break, htf_align=htf_align,
               t_local=t_local, open_time=ot, up1=up1, dn1=dn1, last_ph=last_ph, last_pl=last_pl,
               bull_sweep=bull_sweep, bear_sweep=bear_sweep, eqh=eqh, eql=eql, hour=hour, lowvol=lowvol)

    for d, key in ((1, "l"), (-1, "s")):
        brk = bull_break if d == 1 else bear_break
        lvl = brk_l if d == 1 else brk_s
        leg = leg_l if d == 1 else leg_s
        trig = (brk > 0) & disp & ((c - o) * d > 0) & ~np.isnan(leg) & warm
        if not p.allow_choch:
            trig &= brk == 1
        if p.entry_mode == 1:
            entry = lvl + d * p.entry_offset_atr * atr
        else:
            entry = c.copy()
        sl = leg - d * p.sl_buffer_atr * atr
        dist = (entry - sl) * d
        ok = (dist >= p.sl_min_atr * atr) & (dist <= p.sl_max_atr * atr) & (dist / entry >= p.cost_mult * rt_cost)
        ok &= np.nan_to_num(atr_rank, nan=100.0) <= p.vol_rank_max
        ctx = htf_align * d >= p.htf_min
        opp = up1 if d == 1 else dn1
        opp2 = up2 if d == 1 else dn2
        room_r = (opp - entry) * d / dist
        if p.room_min_r > 0:
            ok &= np.isnan(room_r) | (room_r >= p.room_min_r)
        if p.session_filter:
            ok &= in_session
        if p.lowvol_filter:
            ok &= lowvol
        tp1 = entry + d * p.tp1_r * dist
        tp2 = entry + d * p.tp2_r * dist
        tp3 = entry + d * p.tp3_r * dist
        if p.tp_mode == 1:
            buf = 0.1 * atr
            for lv in (opp, opp2):
                cand = lv - d * buf
                rr = (cand - entry) * d / dist
                use = ~np.isnan(lv) & (rr >= p.min_rr) & (rr <= 5.0) & ((tp2 - entry) * d == p.tp2_r * dist)
                tp2 = np.where(use, cand, tp2)
            tp3 = np.where(d * (tp3 - tp2) < 1.0 * dist, tp2 + d * dist, tp3)
        F = dict(htf_align=htf_align * d, t_local=t_local * d, disp_body=body_frac, disp_range=range_atr,
                 leg_atr=np.abs(np.where(d == 1, h, l) - leg) / atr, risk_atr=dist / atr,
                 atr_rank=np.nan_to_num(atr_rank, nan=50.0), rvol=rvol, pressure=pressure * d,
                 rsi_d=np.nan_to_num(rsi if d == 1 else 100 - rsi, nan=50.0), macd_d=hist * d,
                 room_r=room_r, sweep_recent=((bs_bull_sw if d == 1 else bs_bear_sw) <= 10).astype(float),
                 fvg_new=(fvg_bull_new if d == 1 else fvg_bear_new).astype(float),
                 choch=(brk == 2).astype(float), hhhl_d=(hhhl * d).astype(float))
        w = p.weights if p.weights else DEFAULT_WEIGHTS
        score = score_from_features(F, w)
        setup = trig & ok & ctx
        sig = setup & (score >= p.min_score)
        out.update({f"setup_{key}": setup, f"sig_{key}": sig, f"trig_{key}": trig, f"ok_{key}": ok, f"ctx_{key}": ctx,
                    f"entry_{key}": entry, f"sl_{key}": sl, f"tp1_{key}": tp1, f"tp2_{key}": tp2, f"tp3_{key}": tp3,
                    f"score_{key}": score, f"F_{key}": F, f"dist_{key}": dist})
    # never both directions on one bar (cannot happen with close-based breaks, guard anyway)
    both = out["sig_l"] & out["sig_s"]
    out["sig_l"] &= ~both; out["sig_s"] &= ~both
    return out
