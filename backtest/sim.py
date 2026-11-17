"""
Trade simulator for CFE.

* Entry at the CLOSE of the confirmed signal bar (same as the indicator's ENTRY PRICE and the
  Pine strategy with process_orders_on_close = true).
* Intrabar path follows TradingView's broker-emulator assumption: if the high is closer to the
  open than the low, the path is open->high->low->close, otherwise open->low->high->close.
* Stop modifications (break-even, lock, trailing) take effect from the NEXT bar (as in Pine,
  where strategy.exit levels are re-submitted on bar close).
* Costs: taker fee + slippage on market fills (entry, stop, exit signal, time stop),
  maker fee on TP limit fills (optional), real historical funding for every funding
  timestamp the position is held through.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

REASONS = {1: "SL", 2: "STOP_AFTER_TP", 3: "TP3", 4: "EXIT_SIGNAL", 5: "REVERSE", 6: "TIME", 7: "END"}


@njit(cache=True)
def _fill_cost(px, frac, fee_pct, slip_pct):
    return frac * px * (fee_pct + slip_pct) / 100.0


@njit(cache=True)
def run_trade_ex(i, d, entry, sl0, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_flag, opp_flag,
                 frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                 fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse,
                 k0, seg0, px0, entry_fee, entry_slip):
    """Generic trade walk. The position exists from bar k0: if seg0 < 0 it was opened before the
    open of bar k0 (market entry at the close of bar k0-1); otherwise it was filled inside bar k0
    on path segment seg0 at price px0 (limit entry) and the walk continues from there.
    i = signal bar (used for the time stop)."""
    n = c.shape[0]
    risk = abs(entry - sl0)
    sl = sl0
    rem = 1.0
    pnl = 0.0
    cost = _fill_cost(entry, 1.0, entry_fee, entry_slip)
    fcost = 0.0
    stage = 0
    tp_hit1 = False; tp_hit2 = False
    reason = 7
    ext = entry
    tp_fee = fee_maker if tp_maker else fee_taker
    tp_slip = 0.0 if tp_maker else slip
    j = k0
    exit_bar = n - 1
    for k in range(k0, n):
        j = k
        if abs(h[k] - o[k]) < abs(l[k] - o[k]):
            p1 = h[k]; p2 = l[k]
        else:
            p1 = l[k]; p2 = h[k]
        done = False
        first_seg = 0
        seg_from = o[k]
        if k == k0 and seg0 >= 0:
            first_seg = seg0
            seg_from = px0
        else:
            if fund[k] != 0.0:
                fcost += d * fund[k] * rem * o[k]
            if (o[k] - sl) * d <= 0:
                pnl += rem * d * (o[k] - entry); cost += _fill_cost(o[k], rem, fee_taker, slip); rem = 0.0
                reason = 1 if stage == 0 else 2
                done = True
        if not done:
            for sgi in range(first_seg, 3):
                seg_to = p1 if sgi == 0 else (p2 if sgi == 1 else c[k])
                fav = (seg_to - seg_from) * d > 0
                if fav:
                    if not tp_hit1 and (seg_to - tp1) * d >= 0:
                        px = tp1 if (seg_from - tp1) * d < 0 else seg_from
                        q = frac1
                        pnl += q * d * (px - entry); cost += _fill_cost(px, q, tp_fee, tp_slip); rem -= q
                        tp_hit1 = True; stage = 1
                    if tp_hit1 and not tp_hit2 and (seg_to - tp2) * d >= 0:
                        px = tp2 if (seg_from - tp2) * d < 0 else seg_from
                        q = frac2
                        pnl += q * d * (px - entry); cost += _fill_cost(px, q, tp_fee, tp_slip); rem -= q
                        tp_hit2 = True; stage = 2
                    if tp_hit2 and (seg_to - tp3) * d >= 0:
                        px = tp3 if (seg_from - tp3) * d < 0 else seg_from
                        pnl += rem * d * (px - entry); cost += _fill_cost(px, rem, tp_fee, tp_slip); rem = 0.0
                        stage = 3; reason = 3; done = True
                        break
                else:
                    if (seg_to - sl) * d <= 0:
                        px = sl if (seg_from - sl) * d > 0 else seg_from
                        pnl += rem * d * (px - entry); cost += _fill_cost(px, rem, fee_taker, slip); rem = 0.0
                        reason = 1 if stage == 0 else 2
                        done = True
                        break
                seg_from = seg_to
        if rem <= 1e-9 or done:
            exit_bar = k
            break
        # ---- bar-close decisions ----
        if use_reverse and opp_flag[k]:
            pnl += rem * d * (c[k] - entry); cost += _fill_cost(c[k], rem, fee_taker, slip); rem = 0.0
            reason = 5; exit_bar = k
            break
        if use_exit and exit_flag[k]:
            pnl += rem * d * (c[k] - entry); cost += _fill_cost(c[k], rem, fee_taker, slip); rem = 0.0
            reason = 4; exit_bar = k
            break
        if max_bars > 0 and (k - i) >= max_bars:
            pnl += rem * d * (c[k] - entry); cost += _fill_cost(c[k], rem, fee_taker, slip); rem = 0.0
            reason = 6; exit_bar = k
            break
        # ---- stop management (effective from the next bar) ----
        if d == 1:
            if h[k] > ext:
                ext = h[k]
        else:
            if l[k] < ext:
                ext = l[k]
        if stage >= 1 and be_after_tp1:
            be = entry + d * entry * 2.0 * (fee_taker + slip) / 100.0
            if (be - sl) * d > 0:
                sl = be
        if stage >= 2 and lock_after_tp2:
            if (tp1 - sl) * d > 0:
                sl = tp1
        if stage >= 1 and trail_atr > 0:
            tr = ext - d * trail_atr * atr[k]
            if (tr - sl) * d > 0:
                sl = tr
    if rem > 1e-9:
        pnl += rem * d * (c[j] - entry); cost += _fill_cost(c[j], rem, fee_taker, slip)
        reason = 7; exit_bar = j
    r_gross = pnl / risk
    r_cost = cost / risk
    r_fund = fcost / risk
    r_net = r_gross - r_cost - r_fund
    return exit_bar, r_net, r_gross, r_cost, r_fund, reason, stage


@njit(cache=True)
def run_trade(i, d, entry, sl0, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_flag, opp_flag,
              frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
              fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse):
    """Market entry at the close of bar i."""
    if i + 1 >= c.shape[0]:
        return i, 0.0, 0.0, 0.0, 0.0, 7, 0
    return run_trade_ex(i, d, entry, sl0, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_flag, opp_flag,
                        frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                        fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse,
                        i + 1, -1, 0.0, fee_taker, slip)


@njit(cache=True)
def find_limit_fill(i, d, lim, cancel_lvl, valid_bars, o, h, l, c):
    """Wait for a resting limit order placed at the close of bar i. Fill requires price to trade
    THROUGH the limit (strictly beyond), which is conservative vs. touch fills. The order is cancelled
    if price reaches cancel_lvl first (move left without us) or after valid_bars.
    Returns (k_fill, seg, px) or (-1, -1, 0)."""
    n = c.shape[0]
    for k in range(i + 1, min(n, i + 1 + valid_bars)):
        if abs(h[k] - o[k]) < abs(l[k] - o[k]):
            p1 = h[k]; p2 = l[k]
        else:
            p1 = l[k]; p2 = h[k]
        if (lim - o[k]) * d > 0:          # gapped through the limit at the open
            return k, 0, o[k]
        seg_from = o[k]
        for sgi in range(3):
            seg_to = p1 if sgi == 0 else (p2 if sgi == 1 else c[k])
            if (seg_to - seg_from) * d > 0:
                if (seg_to - cancel_lvl) * d >= 0:
                    return -1, -1, 0.0
            else:
                if (lim - seg_to) * d > 0:
                    return k, sgi, lim
            seg_from = seg_to
    return -1, -1, 0.0


@njit(cache=True)
def run_sequential(sig, entry, sl_l, sl_s, tp1_l, tp2_l, tp3_l, tp1_s, tp2_s, tp3_s,
                   o, h, l, c, atr, fund, exit_l, exit_s, start, end,
                   frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                   fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse, cooldown):
    """One position at a time. sig: +1 long / -1 short / 0. Returns arrays of trades."""
    maxt = 200000
    t_i = np.empty(maxt, np.int64); t_x = np.empty(maxt, np.int64); t_d = np.empty(maxt, np.int8)
    t_r = np.empty(maxt); t_g = np.empty(maxt); t_c = np.empty(maxt); t_f = np.empty(maxt)
    t_reason = np.empty(maxt, np.int8); t_stage = np.empty(maxt, np.int8)
    opp_l = sig == -1
    opp_s = sig == 1
    nt = 0
    i = start
    last_exit = -10**9
    while i < end:
        d = sig[i]
        if d != 0 and (i - last_exit) >= cooldown:
            if d == 1:
                res = run_trade(i, 1, entry[i], sl_l[i], tp1_l[i], tp2_l[i], tp3_l[i], o, h, l, c, atr, fund,
                                exit_l, opp_l, frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                                fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse)
            else:
                res = run_trade(i, -1, entry[i], sl_s[i], tp1_s[i], tp2_s[i], tp3_s[i], o, h, l, c, atr, fund,
                                exit_s, opp_s, frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                                fee_taker, fee_maker, slip, tp_maker, use_exit, use_reverse)
            xb = res[0]
            t_i[nt] = i; t_x[nt] = xb; t_d[nt] = d
            t_r[nt] = res[1]; t_g[nt] = res[2]; t_c[nt] = res[3]; t_f[nt] = res[4]
            t_reason[nt] = res[5]; t_stage[nt] = res[6]
            nt += 1
            if res[5] == 5:
                i = xb            # reversal: opposite signal at the exit bar opens the next trade
                last_exit = -10**9
            else:
                # a new signal on the exit bar's close is allowed only when cooldown == 0
                last_exit = xb
                i = xb if xb > i else i + 1
        else:
            i += 1
    return (t_i[:nt].copy(), t_x[:nt].copy(), t_d[:nt].copy(), t_r[:nt].copy(), t_g[:nt].copy(), t_c[:nt].copy(),
            t_f[:nt].copy(), t_reason[:nt].copy(), t_stage[:nt].copy())


@njit(cache=True)
def run_independent(idx, dirs, entry, sl, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_l, exit_s,
                    frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                    fee_taker, fee_maker, slip, tp_maker, use_exit):
    """Outcome of every candidate as if taken in isolation (for score calibration)."""
    m = idx.shape[0]
    out_r = np.empty(m); out_x = np.empty(m, np.int64); out_reason = np.empty(m, np.int8)
    out_stage = np.empty(m, np.int8); out_c = np.empty(m); out_f = np.empty(m)
    dummy = np.zeros(c.shape[0], np.bool_)
    for t in range(m):
        i = idx[t]; d = dirs[t]
        ef = exit_l if d == 1 else exit_s
        res = run_trade(i, d, entry[t], sl[t], tp1[t], tp2[t], tp3[t], o, h, l, c, atr, fund, ef, dummy,
                        frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr, max_bars,
                        fee_taker, fee_maker, slip, tp_maker, use_exit, False)
        out_x[t] = res[0]; out_r[t] = res[1]; out_c[t] = res[3]; out_f[t] = res[4]
        out_reason[t] = res[5]; out_stage[t] = res[6]
    return out_r, out_x, out_reason, out_stage, out_c, out_f


def funding_to_bars(open_time: np.ndarray, fund_df: pd.DataFrame, bar_ms: int) -> np.ndarray:
    """Map funding events to the bar whose open time is the (rounded) funding timestamp."""
    f = np.zeros(open_time.shape[0])
    if fund_df is None or len(fund_df) == 0:
        return f
    t = fund_df["calc_time"].to_numpy(np.int64)
    t = ((t + bar_ms // 2) // bar_ms) * bar_ms
    idx = np.searchsorted(open_time, t)
    ok = (idx < len(open_time)) & (open_time[np.clip(idx, 0, len(open_time) - 1)] == t)
    np.add.at(f, idx[ok], fund_df["last_funding_rate"].to_numpy(float)[ok])
    return f


def trades_frame(res, open_time, c, bar_ms) -> pd.DataFrame:
    ti, tx, td, tr, tg, tc, tf, treason, tstage = res
    df = pd.DataFrame(dict(entry_bar=ti, exit_bar=tx, dir=td, r_net=tr, r_gross=tg, r_cost=tc, r_fund=tf,
                           reason=[REASONS[int(x)] for x in treason], stage=tstage))
    df["entry_time"] = pd.to_datetime(open_time[ti] + bar_ms, unit="ms", utc=True)
    df["bars"] = tx - ti
    df["entry_px"] = c[ti]
    return df


def stats(tr: pd.DataFrame, risk_pct: float = 1.0, bar_minutes: float = 5.0) -> dict:
    """Performance stats in R and on a fixed-fractional equity curve (risk_pct per trade)."""
    if len(tr) == 0:
        return dict(trades=0)
    r = tr["r_net"].to_numpy()
    g = tr["r_gross"].to_numpy()
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    eq = np.cumprod(1.0 + risk_pct / 100.0 * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    dd = (eq / peak - 1.0).min()
    out = dict(
        trades=int(len(r)),
        win_rate=float((r > 0).mean() * 100),
        avg_r=float(r.mean()),
        avg_r_gross=float(g.mean()),
        avg_cost_r=float(tr["r_cost"].mean()),
        avg_fund_r=float(tr["r_fund"].mean()),
        profit_factor=float(wins / losses) if losses > 0 else float("inf"),
        total_r=float(r.sum()),
        net_profit_pct=float((eq[-1] - 1.0) * 100),
        max_dd_pct=float(dd * 100),
        avg_win_r=float(r[r > 0].mean()) if (r > 0).any() else 0.0,
        avg_loss_r=float(r[r <= 0].mean()) if (r <= 0).any() else 0.0,
        avg_bars=float(tr["bars"].mean()),
        avg_hours=float(tr["bars"].mean() * bar_minutes / 60.0),
        long_trades=int((tr["dir"] == 1).sum()),
        short_trades=int((tr["dir"] == -1).sum()),
        long_avg_r=float(tr.loc[tr["dir"] == 1, "r_net"].mean()) if (tr["dir"] == 1).any() else float("nan"),
        short_avg_r=float(tr.loc[tr["dir"] == -1, "r_net"].mean()) if (tr["dir"] == -1).any() else float("nan"),
    )
    return out


# ======================================================================================
# v2: setups with limit (retest) or market entries
# ======================================================================================
@njit(cache=True)
def _open_trade_v2(i, d, entry, sl, tp1, tp2, tp3, mode, valid_bars, o, h, l, c, atr, fund, exit_flag, dummy,
                   frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip):
    """Returns (filled, k_fill, exit_bar, r_net, r_gross, r_cost, r_fund, reason, stage, fill_px)."""
    if mode == 0:
        if i + 1 >= c.shape[0]:
            return False, -1, i, 0.0, 0.0, 0.0, 0.0, 7, 0, 0.0
        res = run_trade_ex(i, d, c[i], sl, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_flag, dummy,
                           frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip, True, True, False,
                           i + 1, -1, 0.0, fee_t, slip)
        return True, i, res[0], res[1], res[2], res[3], res[4], res[5], res[6], c[i]
    k, sg, px = find_limit_fill(i, d, entry, tp1, valid_bars, o, h, l, c)
    if k < 0:
        return False, -1, i, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0
    # R levels are anchored to the planned entry/SL (what the user sees); fill px may be better on gaps
    res = run_trade_ex(i, d, px, sl, tp1, tp2, tp3, o, h, l, c, atr, fund, exit_flag, dummy,
                       frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip, True, True, False,
                       k, sg, px, fee_m, 0.0)
    return True, k, res[0], res[1], res[2], res[3], res[4], res[5], res[6], px


@njit(cache=True)
def run_sequential_v2(sig, entry_l, sl_l, tp1_l, tp2_l, tp3_l, entry_s, sl_s, tp1_s, tp2_s, tp3_s,
                      mode, valid_bars, o, h, l, c, atr, fund, start, end,
                      frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip, exit_on_opp):
    maxt = 60000
    T = np.zeros((maxt, 11))
    nt = 0
    n = c.shape[0]
    opp_l = sig == -1
    opp_s = sig == 1
    noexit = np.zeros(n, np.bool_)
    i = start
    while i < end:
        d = sig[i]
        if d == 0:
            i += 1
            continue
        if d == 1:
            e = entry_l[i]; s = sl_l[i]; a = tp1_l[i]; b = tp2_l[i]; cc = tp3_l[i]
            ef = opp_l if exit_on_opp else noexit
        else:
            e = entry_s[i]; s = sl_s[i]; a = tp1_s[i]; b = tp2_s[i]; cc = tp3_s[i]
            ef = opp_s if exit_on_opp else noexit
        # a newer setup before the fill replaces a pending limit order
        vb = valid_bars
        if mode == 1:
            for m in range(i + 1, min(n, i + 1 + valid_bars)):
                if sig[m] != 0:
                    vb = m - i      # pending order may fill up to (and including) bar m intrabar
                    break
        res = _open_trade_v2(i, d, e, s, a, b, cc, mode, vb, o, h, l, c, atr, fund, ef, noexit,
                             frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip)
        filled = res[0]
        if not filled:
            # move to the replacing setup (if any) or past the expiry window
            nxt = i + 1
            while nxt < min(n, i + 1 + valid_bars) and sig[nxt] == 0:
                nxt += 1
            i = nxt
            continue
        xb = res[2]
        T[nt, 0] = i; T[nt, 1] = res[1]; T[nt, 2] = xb; T[nt, 3] = d; T[nt, 4] = res[3]; T[nt, 5] = res[4]
        T[nt, 6] = res[5]; T[nt, 7] = res[6]; T[nt, 8] = res[7]; T[nt, 9] = res[8]; T[nt, 10] = res[9]
        nt += 1
        i = xb if xb > i else i + 1     # a new setup may form on the exit bar's close
        if mode == 0 and res[7] == 5:
            pass
    return T[:nt].copy()


@njit(cache=True)
def run_independent_v2(idx, dirs, entry, sl, tp1, tp2, tp3, mode, valid_bars, o, h, l, c, atr, fund,
                       frac1, frac2, be, lock, trail, max_bars, fee_t, fee_m, slip):
    m = idx.shape[0]
    out = np.full((m, 8), np.nan)
    noexit = np.zeros(c.shape[0], np.bool_)
    for t in range(m):
        res = _open_trade_v2(idx[t], dirs[t], entry[t], sl[t], tp1[t], tp2[t], tp3[t], mode, valid_bars,
                             o, h, l, c, atr, fund, noexit, noexit, frac1, frac2, be, lock, trail, max_bars,
                             fee_t, fee_m, slip)
        out[t, 0] = 1.0 if res[0] else 0.0
        if res[0]:
            out[t, 1] = res[3]; out[t, 2] = res[4]; out[t, 3] = res[5]; out[t, 4] = res[6]
            out[t, 5] = res[2] - idx[t]; out[t, 6] = res[7]; out[t, 7] = res[1]
    return out


V2_COLS = ["sig_bar", "fill_bar", "exit_bar", "dir", "r_net", "r_gross", "r_cost", "r_fund", "reason", "stage", "fill_px"]


def trades_v2(T, open_time, bar_ms) -> pd.DataFrame:
    df = pd.DataFrame(T, columns=V2_COLS)
    for k in ("sig_bar", "fill_bar", "exit_bar", "dir", "reason", "stage"):
        df[k] = df[k].astype(int)
    df["reason"] = [REASONS.get(int(x), "?") for x in df["reason"]]
    df["entry_time"] = pd.to_datetime(open_time[df["sig_bar"].to_numpy()] + bar_ms, unit="ms", utc=True)
    df["bars"] = df["exit_bar"] - df["fill_bar"]
    return df
