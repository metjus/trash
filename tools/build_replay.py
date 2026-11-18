"""
Build the data for the visual replay page (docs page / artifact): a real window of the reference engine
on Binance data, bar by bar, including the forming-candle PREVIEW from real 5m sub-bars.

    PYTHONPATH=. CFE_DATA_DIR=<cache> python tools/build_replay.py --out replay.json

Consistency checks (asserted): the structure/liquidity mirror reproduces the engine's BOS/CHoCH/sweeps/state in
the window, and the bar-by-bar tracker reproduces run_sequential_v2's trades (fill bar, exit bar, gross R).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from backtest import cfe, dataset as ds, engine, indicators as ind, sim, walkforward as wf

SYM, TF = "BTCUSDT", "15m"
W0, W1 = "2026-04-15 22:00", "2026-04-18 00:00"   # window (UTC, bar open times)
BAR = 900_000


def params():
    return cfe.P2(htf_list=("1h", "4h"), htf_weights=(1.5, 2.0), htf_min=1.0, min_score=70.0,
                  weights=wf.FINAL_WEIGHTS, session_filter=True, entry_mode=1)


# --------------------------------------------------------------------------------------------
# structure mirror with object logging (same rules/order as engine.structure_pass)
# --------------------------------------------------------------------------------------------
def structure_log(o, h, l, c, atr, rsi, a, b, L=5, slots=10, eq_tol=0.15, fvg_min=0.25, obs=50, htf=None, prm=None):
    pools = {"H": [None] * slots, "L": [None] * slots}     # each: dict(level, pbar, cbar)
    zones = {k: [None] * 5 for k in ("bF", "sF", "bO", "sO")}
    objs, events = [], []
    last = {"H": np.nan, "L": np.nan}; prev = {"H": np.nan, "L": np.nan}
    lastbar = {"H": -1, "L": -1}; broken = {"H": True, "L": True}; lrsi = {"H": np.nan, "L": np.nan}
    state = 0; div = {"bull": -10**9, "bear": -10**9}
    out = {k: np.zeros(b - a, np.int8) for k in ("ms", "bb", "sb", "bsw", "ssw", "hhhl", "bdiv", "sdiv")}
    out["sc"] = [None] * (b - a)
    win = 2 * L + 1

    def push_pool(side, lvl, pbar, i):
        arr = pools[side]
        k = next((s for s in range(slots) if arr[s] is None), -1)
        obj = dict(kind="liqH" if side == "H" else "liqL", level=float(lvl), x0=int(pbar), born=int(i), end=None, how=None)
        objs.append(obj)
        if k == -1:
            old = arr.pop(0)
            if old is not None and old["end"] is None:
                old["end"] = int(i); old["how"] = "dropped"
            arr.append(obj)
        else:
            arr[k] = obj

    def push_zone(key, top, bot, left, i):
        arr = zones[key]
        old = arr.pop(0)
        if old is not None and old["end"] is None:
            old["end"] = int(i)
        obj = dict(kind=key, top=float(top), bot=float(bot), x0=int(left), born=int(i), end=None)
        objs.append(obj); arr.append(obj)

    for i in range(a, b):
        A = atr[i]
        eqh = eql = False
        if i >= win - 1 and not np.isnan(A):
            p = i - L
            isph = h[p] >= h[i - win + 1:i + 1].max()
            ispl = l[p] <= l[i - win + 1:i + 1].min()
            for side, flag in (("H", isph), ("L", ispl)):
                if not flag:
                    continue
                v = h[p] if side == "H" else l[p]
                prev[side] = last[side]; last[side] = v; lastbar[side] = p; broken[side] = False
                if not np.isnan(prev[side]) and abs(v - prev[side]) <= eq_tol * A:
                    if side == "H": eqh = True
                    else: eql = True
                if side == "H" and not np.isnan(prev["H"]) and v > prev["H"] and not np.isnan(lrsi["H"]) and rsi[p] < lrsi["H"]:
                    div["bear"] = i
                if side == "L" and not np.isnan(prev["L"]) and v < prev["L"] and not np.isnan(lrsi["L"]) and rsi[p] > lrsi["L"]:
                    div["bull"] = i
                lrsi[side] = rsi[p]
                push_pool(side, v, p, i)
                if (eqh if side == "H" else eql):
                    events.append(dict(bar=int(i), type="EQH" if side == "H" else "EQL", x=int(p), price=float(v)))
        hh = 0
        if not np.isnan(prev["H"]) and not np.isnan(prev["L"]):
            if last["H"] > prev["H"] and last["L"] > prev["L"]: hh = 1
            elif last["H"] < prev["H"] and last["L"] < prev["L"]: hh = -1
        bsw = ssw = False
        for s in range(slots):
            o_ = pools["L"][s]
            if o_ is not None and l[i] < o_["level"]:
                if c[i] > o_["level"]:
                    bsw = True; o_["how"] = "sweep"
                else:
                    o_["how"] = "break"
                o_["end"] = int(i); pools["L"][s] = None
            o_ = pools["H"][s]
            if o_ is not None and h[i] > o_["level"]:
                if c[i] < o_["level"]:
                    ssw = True; o_["how"] = "sweep"
                else:
                    o_["how"] = "break"
                o_["end"] = int(i); pools["H"][s] = None
        if bsw: events.append(dict(bar=int(i), type="SWEEP_BULL", price=float(l[i])))
        if ssw: events.append(dict(bar=int(i), type="SWEEP_BEAR", price=float(h[i])))
        bb = sb = 0
        if not broken["H"] and not np.isnan(last["H"]) and c[i] > last["H"]:
            broken["H"] = True
            bb = 2 if state == -1 else 1; state = 1
            events.append(dict(bar=int(i), type="CHOCH_UP" if bb == 2 else "BOS_UP", x=int(lastbar["H"]), price=float(last["H"])))
            lo = max(lastbar["L"], i - obs, 0)
            for j in range(i - 1, lo - 1, -1):
                if c[j] < o[j]:
                    push_zone("bO", h[j], l[j], j, i); break
        if not broken["L"] and not np.isnan(last["L"]) and c[i] < last["L"]:
            broken["L"] = True
            sb = 2 if state == 1 else 1; state = -1
            events.append(dict(bar=int(i), type="CHOCH_DN" if sb == 2 else "BOS_DN", x=int(lastbar["L"]), price=float(last["L"])))
            lo = max(lastbar["H"], i - obs, 0)
            for j in range(i - 1, lo - 1, -1):
                if c[j] > o[j]:
                    push_zone("sO", h[j], l[j], j, i); break
        if i >= 2 and not np.isnan(A):
            if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= fvg_min * A:
                push_zone("bF", l[i], h[i - 2], i - 2, i)
            if h[i] < l[i - 2] and (l[i - 2] - h[i]) >= fvg_min * A:
                push_zone("sF", l[i - 2], h[i], i - 2, i)
        for s in range(5):
            for key in ("bF", "bO"):
                z = zones[key][s]
                if z is not None and z["end"] is None and c[i] < z["bot"]:
                    z["end"] = int(i); zones[key][s] = None
            for key in ("sF", "sO"):
                z = zones[key][s]
                if z is not None and z["end"] is None and c[i] > z["top"]:
                    z["end"] = int(i); zones[key][s] = None
        k = i - a
        out["ms"][k] = state; out["bb"][k] = bb; out["sb"][k] = sb; out["bsw"][k] = bsw; out["ssw"][k] = ssw
        out["hhhl"][k] = hh; out["bdiv"][k] = (i - div["bull"]) < 10; out["sdiv"][k] = (i - div["bear"]) < 10
        if htf is not None:
            # LONG / SHORT scenario – identical to f_scen() in the Pine indicator
            rt = 2 * (prm.fee_taker + prm.slippage) / 100
            sc = []
            for d, side, other in ((1, "H", "L"), (-1, "L", "H")):
                if broken[side] or np.isnan(last[side]):
                    sc.append([0, None, None, None, None]); continue
                trig = float(last[side]); lo = max(lastbar[other], i - obs, 0)
                ext = float(l[lo:i + 1].min() if d == 1 else h[lo:i + 1].max())
                slv = ext - d * prm.sl_buffer_atr * A
                dist = (trig - slv) * d
                okd = bool(dist >= prm.sl_min_atr * A and dist <= prm.sl_max_atr * A and dist / trig >= prm.cost_mult * rt)
                ctx = bool(d * htf[i] >= prm.htf_min - 1e-9)
                st = 1 if (ctx and okd) else (2 if not ctx else 3)
                sc.append([st, trig, int(lastbar[side]), float(slv), float(trig + d * prm.tp3_r * dist)])
            out["sc"][k] = sc
    return out, objs, events


# --------------------------------------------------------------------------------------------
# bar-by-bar tracker (mirror of the Pine TRADE TRACKER)
# --------------------------------------------------------------------------------------------
def path(o, h, l, c):
    return [o, h, l, c] if abs(h - o) < abs(l - o) else [o, l, h, c]


def track(R, a, b, p):
    O, H, L, C = R["o"], R["h"], R["l"], R["c"]
    sig = np.where(R["sig_l"], 1, np.where(R["sig_s"], -1, 0))
    tr = None
    events, states, trades = [], [], []
    f1 = f2 = 1 / 3
    for k in range(a, b):
        pts = path(O[k], H[k], L[k], C[k])
        if tr is not None:
            d = tr["dir"]
            closed = False
            seg0, px0 = None, None
            if tr["state"] == 1:
                filled = cancel = False
                if (tr["planned"] - O[k]) * d > 0:
                    filled, seg0, px0 = True, 0, O[k]
                else:
                    for s in range(3):
                        x0, x1 = pts[s], pts[s + 1]
                        if (x1 - x0) * d > 0:
                            if (x1 - tr["tp1"]) * d >= 0:
                                cancel = True; break
                        elif (tr["planned"] - x1) * d > 0:
                            filled, seg0, px0 = True, s, tr["planned"]; break
                if filled:
                    tr.update(state=2, fill=k, entry=px0)
                    events.append(dict(bar=k, type="FILLED", price=float(px0), dir=d))
                elif cancel or k - tr["setup"] >= p.valid_bars:
                    events.append(dict(bar=k, type="CANCEL" if cancel else "EXPIRED", price=float(H[k] if d == -1 else L[k]), dir=d))
                    tr["end"] = k; tr["outcome"] = "CANCEL" if cancel else "EXPIRED"; trades.append(tr)
                    tr = None; closed = True
            elif tr["state"] == 2:
                seg0, px0 = -1, O[k]
            if tr is not None and tr["state"] == 2 and seg0 is not None:
                risk = abs(tr["entry"] - tr["sl0"])
                cur = px0
                exit_px = None
                if seg0 == -1:
                    if (O[k] - tr["sl"]) * d <= 0:
                        exit_px = O[k]
                    segs = range(3)
                else:
                    segs = range(seg0, 3)
                if exit_px is None:
                    for s in segs:
                        x1 = pts[s + 1]
                        if (x1 - cur) * d > 0:
                            if tr["stage"] == 0 and (x1 - tr["tp1"]) * d >= 0:
                                tr["stage"] = 1; tr["pnl"] += f1 * d * (tr["tp1"] - tr["entry"]); tr["rem"] -= f1
                                events.append(dict(bar=k, type="TP1", price=float(tr["tp1"]), dir=d))
                            if tr["stage"] == 1 and (x1 - tr["tp2"]) * d >= 0:
                                tr["stage"] = 2; tr["pnl"] += f2 * d * (tr["tp2"] - tr["entry"]); tr["rem"] -= f2
                                events.append(dict(bar=k, type="TP2", price=float(tr["tp2"]), dir=d))
                            if tr["stage"] == 2 and (x1 - tr["tp3"]) * d >= 0:
                                tr["pnl"] += tr["rem"] * d * (tr["tp3"] - tr["entry"]); tr["rem"] = 0
                                events.append(dict(bar=k, type="TP3", price=float(tr["tp3"]), dir=d))
                                tr["outcome"] = "TP3"; break
                        elif (x1 - tr["sl"]) * d <= 0:
                            exit_px = tr["sl"] if (cur - tr["sl"]) * d > 0 else cur
                            break
                        cur = x1
                if exit_px is not None:
                    tr["pnl"] += tr["rem"] * d * (exit_px - tr["entry"]); tr["rem"] = 0
                    kind = "SL" if tr["stage"] == 0 else "STOP"
                    events.append(dict(bar=k, type=kind, price=float(exit_px), dir=d))
                    tr["outcome"] = kind
                if tr["rem"] <= 1e-9:
                    tr["end"] = k; tr["r_gross"] = tr["pnl"] / risk; trades.append(tr)
                    states.append(snapshot(tr, k, closed_now=True))
                    tr = None; closed = True
                else:
                    if tr["stage"] >= 1:
                        be = tr["entry"] + d * tr["entry"] * 2 * (p.fee_taker + p.slippage) / 100
                        if (be - tr["sl"]) * d > 0:
                            tr["sl"] = be
                            events.append(dict(bar=k, type="BE", price=float(be), dir=d))
                    if tr["stage"] >= 2 and (tr["tp1"] - tr["sl"]) * d > 0:
                        tr["sl"] = tr["tp1"]
                        events.append(dict(bar=k, type="LOCK", price=float(tr["tp1"]), dir=d))
            if closed and not any(s["bar"] == k for s in states):
                pass
        # new signal
        if sig[k] != 0 and (tr is None or tr["state"] == 1):
            if tr is not None:
                events.append(dict(bar=k, type="REPLACED", price=float(C[k]), dir=tr["dir"]))
                tr["end"] = k; tr["outcome"] = "REPLACED"; trades.append(tr)
            d = int(sig[k]); key = "l" if d == 1 else "s"
            tr = dict(dir=d, state=1, setup=k, fill=None, planned=float(R[f"entry_{key}"][k]), entry=float(R[f"entry_{key}"][k]),
                      sl=float(R[f"sl_{key}"][k]), sl0=float(R[f"sl_{key}"][k]), tp1=float(R[f"tp1_{key}"][k]),
                      tp2=float(R[f"tp2_{key}"][k]), tp3=float(R[f"tp3_{key}"][k]), score=float(R[f"score_{key}"][k]),
                      stage=0, rem=1.0, pnl=0.0, end=None, outcome=None)
            comps = cfe.score_components({kk: np.array([v[k]]) for kk, v in R[f"F_{key}"].items()})
            tr["comps"] = {kk: float(np.asarray(v).ravel()[0]) for kk, v in comps.items()}
            tr["inval"] = float(tr["sl0"] + d * p.sl_buffer_atr * R["atr"][k])
            tr["htf"] = float(R["htf_align"][k] * d)
            tr["trigger"] = "CHoCH" if (R["bull_break"][k] if d == 1 else R["bear_break"][k]) == 2 else "BOS"
            events.append(dict(bar=k, type="LONG" if d == 1 else "SHORT", price=float(L[k] if d == 1 else H[k]), dir=d,
                               score=tr["score"]))
        if not any(s["bar"] == k for s in states):
            states.append(snapshot(tr, k))
    if tr is not None:
        trades.append(tr)
    return events, states, trades


def snapshot(tr, k, closed_now=False):
    if tr is None:
        return dict(bar=k, st=0)
    return dict(bar=k, st=0 if closed_now else tr["state"], dir=tr["dir"], setup=tr["setup"], entry=tr["entry"], sl=tr["sl"],
                tp1=tr["tp1"], tp2=tr["tp2"], tp3=tr["tp3"], stage=tr["stage"], rem=tr["rem"], score=tr["score"],
                realized=tr["pnl"] / abs(tr["entry"] - tr["sl0"]), sl0=tr["sl0"])


def main(out):
    p = params()
    df5, fd = ds.load(SYM)
    chart = ds.chart(df5, TF)
    R = cfe.compute(chart, p, base_df=df5, chart_tf=TF)
    ot = R["open_time"]
    a = int(np.searchsorted(ot, pd.Timestamp(W0, tz="UTC").value // 10**6))
    b = int(np.searchsorted(ot, pd.Timestamp(W1, tz="UTC").value // 10**6))
    O, H, L, C, V = R["o"], R["h"], R["l"], R["c"], R["v"]

    # ---- structure mirror (warm-up 4000 bars) + consistency check vs engine ----
    w0 = a - 4000
    rsi = np.nan_to_num(R["rsi"], nan=50.0)
    mo, objs, sev = structure_log(O, H, L, C, R["atr"], rsi, w0, b, htf=R["htf_align"], prm=p)
    off = a - w0
    assert np.array_equal(mo["ms"][off:], R["ms"][a:b]), "ms mismatch"
    assert np.array_equal(mo["bb"][off:], R["bull_break"][a:b]), "bull break mismatch"
    assert np.array_equal(mo["sb"][off:], R["bear_break"][a:b]), "bear break mismatch"
    assert np.array_equal(mo["bsw"][off:].astype(bool), R["bull_sweep"][a:b]), "sweep mismatch"
    assert np.array_equal(mo["ssw"][off:].astype(bool), R["bear_sweep"][a:b]), "sweep mismatch"

    # ---- tracker + consistency check vs run_sequential_v2 ----
    events, states, trades = track(R, a, b, p)
    fund = np.zeros(len(C))
    sig = np.where(R["sig_l"], 1, np.where(R["sig_s"], -1, 0)).astype(np.int8)
    T = sim.run_sequential_v2(sig, R["entry_l"], R["sl_l"], R["tp1_l"], R["tp2_l"], R["tp3_l"],
                              R["entry_s"], R["sl_s"], R["tp1_s"], R["tp2_s"], R["tp3_s"], 1, p.valid_bars,
                              O, H, L, C, R["atr"], fund, a, b, 1 / 3, 1 / 3, True, True, 0.0, 0,
                              p.fee_taker, p.fee_maker, p.slippage, False)
    filled = [t for t in trades if t.get("fill") is not None and t.get("r_gross") is not None]
    assert len(filled) == len(T), (len(filled), len(T))
    for t, row in zip(filled, T):
        assert t["setup"] == int(row[0]) and t["fill"] == int(row[1]) and t["end"] == int(row[2]), (t, row)
        assert abs(t["r_gross"] - row[5]) < 1e-9, (t["r_gross"], row[5])
    net_r = {int(row[0]): float(row[4]) for row in T}
    # every real signal must have been announced by the scenario trigger on the previous bar
    for t in trades:
        k = t["setup"]; d = t["dir"]
        sc_prev = mo["sc"][k - 1 - w0][0 if d == 1 else 1]
        assert sc_prev[0] > 0 and abs(sc_prev[1] - t["planned"]) < 1e-9, ("scenario trigger mismatch", k, sc_prev, t["planned"])

    # ---- MTF states ----
    s1h = engine.htf_state_aligned(chart, df5, "1h", p)
    s4h = engine.htf_state_aligned(chart, df5, "4h", p)
    t5 = engine.trend_state(df5["close"].to_numpy(float), p)
    ot5 = df5["open_time"].to_numpy(np.int64)

    def s5_at(open_ms):
        idx = np.searchsorted(ot5, open_ms)
        return float(t5[idx]) if idx < len(ot5) and ot5[idx] == open_ms else None

    ema20 = ind.ema(C, 20); ema50 = ind.ema(C, 50); ema200 = ind.ema(C, 200)
    hist = R["hist"]

    # ---- forming candle (real 5m sub-bars) + PREVIEW from the engine on the partial bar ----
    hist_start = pd.Timestamp("2025-06-01", tz="UTC")
    base = df5[df5["time"] >= hist_start].reset_index(drop=True)
    bot5 = base["open_time"].to_numpy(np.int64)
    bars = []
    for i in range(a, b):
        t0 = int(ot[i])
        subs = []
        for m in (1, 2):
            cut = t0 + m * 300_000
            j = int(np.searchsorted(bot5, cut))
            part = base.iloc[j - m:j]
            po, ph, pl, pc = float(part["open"].iloc[0]), float(part["high"].max()), float(part["low"].min()), float(part["close"].iloc[-1])
            bt = base.iloc[:j]
            ch = engine.resample(bt, TF)
            Rp = cfe.compute(ch, p, base_df=bt, chart_tf=TF)
            n = len(ch) - 1
            assert int(ch["open_time"].iloc[-1]) == t0
            pv = None
            if Rp["setup_l"][n] or Rp["setup_s"][n]:
                d = 1 if Rp["setup_l"][n] else -1
                key = "l" if d == 1 else "s"
                pv = dict(dir=d, score=round(float(Rp[f"score_{key}"][n]), 1))
            subs.append(dict(o=po, h=ph, l=pl, c=pc, s5=s5_at(t0 + (m - 1) * 300_000), pv=pv))
        # sanity: the engine on the FULL bar from the truncated history agrees with the full-history run
        bars.append(dict(t=t0, o=float(O[i]), h=float(H[i]), l=float(L[i]), c=float(C[i]), v=float(V[i]),
                         e20=float(ema20[i]), e50=float(ema50[i]), e200=float(ema200[i]),
                         htf=float(R["htf_align"][i]), tl=float(R["t_local"][i]), s1h=float(s1h[i]), s4h=float(s4h[i]),
                         s5=s5_at(t0 + 600_000), ms=int(R["ms"][i]), hh=int(mo["hhhl"][i - w0]),
                         bdiv=bool(mo["bdiv"][i - w0]), sdiv=bool(mo["sdiv"][i - w0]),
                         atrp=float(R["atr"][i] / C[i] * 100), rank=float(R["atr_rank"][i]), rvol=float(R["rvol"][i]),
                         press=float(R["pressure"][i]), rsi=float(R["rsi"][i]), macd=float(hist[i]),
                         sess=bool(R["lowvol"][i] if False else ((((ot[i] + BAR - 1) // 3_600_000) % 24) >= 13)),
                         sc=[[x[0], x[1], None if x[2] is None else x[2] - a, x[3], x[4]] for x in mo["sc"][i - w0]],
                         subs=subs))
        if (i - a) % 40 == 0:
            print("partial bars", i - a, "/", b - a, flush=True)

    # full-bar check of the truncated-history engine at the signal bars
    for t in trades:
        k = t["setup"]
        j = int(np.searchsorted(bot5, int(ot[k]) + BAR))
        bt = base.iloc[:j]; ch = engine.resample(bt, TF)
        Rp = cfe.compute(ch, p, base_df=bt, chart_tf=TF)
        key = "l" if t["dir"] == 1 else "s"
        assert Rp[f"sig_{key}"][len(ch) - 1], "truncated-history engine disagrees at a signal bar"

    # why a structure break did / did not become a signal (same checks as cfe.compute)
    rt = 2 * (p.fee_taker + p.slippage) / 100
    for i in range(a, b):
        why = []
        for d, key, brk in ((1, "l", R["bull_break"]), (-1, "s", R["bear_break"])):
            if brk[i] == 0:
                continue
            rng = H[i] - L[i]
            body = abs(C[i] - O[i]) / rng if rng > 0 else 0.0
            disp = body >= p.disp_body and rng >= p.disp_range_atr * R["atr"][i] and (C[i] - O[i]) * d > 0
            dist = R[f"dist_{key}"][i]
            dist_ok = bool(dist >= p.sl_min_atr * R["atr"][i] and dist <= p.sl_max_atr * R["atr"][i]) if not np.isnan(dist) else False
            cost_ok = bool(dist / R[f"entry_{key}"][i] >= p.cost_mult * rt) if not np.isnan(dist) else False
            hour_c = ((ot[i] + BAR - 1) // 3_600_000) % 24
            why.append(dict(dir=d, kind="CHoCH" if brk[i] == 2 else "BOS", disp=bool(disp), body=round(float(body), 2),
                            rng=round(float(rng / R["atr"][i]), 2), htf=round(float(R["htf_align"][i] * d), 2),
                            sess=bool(13 <= hour_c < 24), dist=dist_ok, cost=cost_ok,
                            vol=bool(np.nan_to_num(R["atr_rank"][i], nan=100) <= p.vol_rank_max),
                            score=round(float(R[f"score_{key}"][i]), 1), signal=bool(R[f"sig_{key}"][i])))
        bars[i - a]["why"] = why

    # objects visible in the window
    keep = [o_ for o_ in objs if (o_["end"] is None or o_["end"] >= a) and o_["born"] < b and o_["born"] >= a - 400]
    for o_ in keep:
        for kk in ("x0", "born", "end"):
            if o_[kk] is not None:
                o_[kk] = int(o_[kk]) - a
    sev = [dict(e, bar=e["bar"] - a, **({"x": e["x"] - a} if "x" in e else {})) for e in sev if a <= e["bar"] < b]
    ev_ = [dict(e, bar=int(e["bar"]) - a) for e in events]
    st_ = [dict(s, bar=int(s["bar"]) - a, **({"setup": s["setup"] - a} if "setup" in s else {})) for s in states]
    tr_ = []
    for t in trades:
        tr_.append(dict(dir=t["dir"], setup=t["setup"] - a, fill=None if t["fill"] is None else t["fill"] - a,
                        end=None if t["end"] is None else t["end"] - a, outcome=t["outcome"], planned=t["planned"],
                        entry=t["entry"], sl=t["sl0"], inval=t["inval"], tp1=t["tp1"], tp2=t["tp2"], tp3=t["tp3"],
                        score=t["score"], comps=t["comps"], htf=t["htf"], trigger=t["trigger"],
                        r_gross=t.get("r_gross"), r_net=net_r.get(t["setup"])))

    # ---- validation summary for the results section ----
    fr = json.load(open("results/final_results.json"))
    h2 = json.load(open("results/holdout2_results.json"))
    ho = pd.read_csv("results/holdout_trades_15m.csv", parse_dates=["entry_time"]).sort_values("entry_time")
    eqn = np.cumprod(1 + 0.005 * ho["r_net"].to_numpy()); eqg = np.cumprod(1 + 0.005 * ho["r_gross"].to_numpy())
    step = max(1, len(ho) // 500)
    idx = list(range(0, len(ho), step)) + [len(ho) - 1]
    equity = [dict(t=int(ho["entry_time"].iloc[k].value // 10**6), n=round(float(eqn[k]), 4), g=round(float(eqg[k]), 4), i=k + 1) for k in idx]
    summ = []
    for name, s in (("15m · holdout 1", fr["pre_15m_holdout"]), ("15m · holdout 2", h2["15m_A_default"]),
                    ("5m · holdout 1", fr["pre_5m_holdout"]), ("5m · holdout 2", h2["5m_A_default"])):
        summ.append(dict(name=name, trades=s["trades"], win=s["win_rate_pct"], gross=s["avg_R_gross"], cost=round(s["avg_cost_R"] + s["avg_funding_R"], 3),
                         net=s["avg_R_net"], pf=s["profit_factor"], t=s["t_stat"]))

    data = dict(symbol="BINANCE:BTCUSDT.P", tf="15m", bars=bars, objects=keep, structEvents=sev, events=ev_, states=st_,
                trades=tr_, equity=equity, summary=summ,
                costs=dict(taker=p.fee_taker, maker=p.fee_maker, slip=p.slippage))
    def rnd(x):
        if isinstance(x, float):
            return round(x, 2) if abs(x) >= 100 else round(x, 4)
        if isinstance(x, dict):
            return {k: rnd(v) for k, v in x.items()}
        if isinstance(x, list):
            return [rnd(v) for v in x]
        return x
    data = rnd(data)
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print("bars", len(bars), "objects", len(keep), "events", len(ev_), "trades", [(t["outcome"], t["r_net"]) for t in tr_])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="replay.json")
    main(ap.parse_args().out)
