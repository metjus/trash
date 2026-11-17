"""
Cross-check of the numba simulator against an independent, deliberately simple pure-Python
re-implementation of the same trade rules (limit retest entry, 1/3-1/3-1/3 partials, BE after TP1,
lock after TP2, TradingView OHLC path assumption). Gross R must match for every sampled trade.
"""
import os

import numpy as np
import pytest

from backtest import cfe, dataset as ds, engine, sim, walkforward as wf


def path(o, h, l, c):
    return [o, h, l, c] if abs(h - o) < abs(l - o) else [o, l, h, c]


def simple_trade(i, d, E, SL, T1, T2, T3, O, H, L, C, valid, fee_t, slip):
    n = len(C)
    # wait for fill
    k_fill = None
    for k in range(i + 1, min(n, i + 1 + valid)):
        pts = path(O[k], H[k], L[k], C[k])
        if (E - pts[0]) * d > 0:
            k_fill, seg, px = k, 0, pts[0]
            break
        hit = None
        for s in range(3):
            a, b = pts[s], pts[s + 1]
            if (b - a) * d > 0 and (b - T1) * d >= 0:
                hit = "cancel"; break
            if (b - a) * d <= 0 and (E - b) * d > 0:
                hit = ("fill", s); break
        if hit == "cancel":
            return None
        if hit:
            k_fill, seg, px = k, hit[1], E
            break
    if k_fill is None:
        return None
    entry = px; risk = abs(entry - SL); sl = SL; rem = 1.0; pnl = 0.0; stage = 0
    k = k_fill
    first = True
    while k < n:
        pts = path(O[k], H[k], L[k], C[k])
        if first:
            cur = px; segs = range(seg, 3)
        else:
            cur = pts[0]; segs = range(3)
            if (cur - sl) * d <= 0:
                pnl += rem * d * (cur - entry); return pnl / risk
        for s in segs:
            b = pts[s + 1]
            if (b - cur) * d > 0:
                if stage == 0 and (b - T1) * d >= 0:
                    pnl += (1 / 3) * d * (T1 - entry); rem -= 1 / 3; stage = 1
                if stage == 1 and (b - T2) * d >= 0:
                    pnl += (1 / 3) * d * (T2 - entry); rem -= 1 / 3; stage = 2
                if stage == 2 and (b - T3) * d >= 0:
                    pnl += rem * d * (T3 - entry); return pnl / risk
            else:
                if (b - sl) * d <= 0:
                    pnl += rem * d * (sl - entry); return pnl / risk
            cur = b
        first = False
        if stage >= 1:
            be = entry + d * entry * 2 * (fee_t + slip) / 100
            if (be - sl) * d > 0: sl = be
        if stage >= 2 and (T1 - sl) * d > 0:
            sl = T1
        k += 1
    pnl += rem * d * (C[-1] - entry)
    return pnl / risk


def test_crosscheck():
    if not os.environ.get("CFE_DATA_DIR"):
        pytest.skip("set CFE_DATA_DIR")
    df5, fd = ds.load("ETHUSDT")
    df5 = df5[(df5["time"] >= "2024-01-01") & (df5["time"] < "2024-07-01")].reset_index(drop=True)
    hl = wf.htf_lists("5m")["base"]
    p = cfe.P2(htf_list=hl, htf_weights=tuple(wf.HTF_W[x] for x in hl), htf_min=-9, min_score=0, cost_mult=0)
    R = cfe.compute(df5, p, base_df=df5, chart_tf="5m")
    O, H, L, C = R["o"], R["h"], R["l"], R["c"]
    fund = np.zeros(len(C))
    checked = 0
    for d, key in ((1, "l"), (-1, "s")):
        idx = np.nonzero(R[f"setup_{key}"])[0][:150]
        E = R[f"entry_{key}"][idx]; S = R[f"sl_{key}"][idx]
        dist = np.abs(E - S)
        T1, T2, T3 = E + d * dist, E + d * 2 * dist, E + d * 3 * dist
        out = sim.run_independent_v2(idx.astype(np.int64), np.full(len(idx), d, np.int8), E, S, T1, T2, T3, 1, 12,
                                     O, H, L, C, R["atr"], fund, 1 / 3, 1 / 3, True, True, 0.0, 0, 0.05, 0.02, 0.02)
        for t, i in enumerate(idx):
            ref = simple_trade(i, d, E[t], S[t], T1[t], T2[t], T3[t], O, H, L, C, 12, 0.05, 0.02)
            if ref is None:
                assert out[t, 0] == 0
            else:
                assert out[t, 0] == 1
                assert abs(out[t, 2] - ref) < 1e-6, (i, d, out[t, 2], ref)
                checked += 1
    assert checked > 100
