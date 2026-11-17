"""
Walk-forward analysis for CFE v2.

* Parameters are chosen on a rolling TRAIN window (pooled across all symbols, one common
  parameter set - more robust than per-symbol fitting), then applied unchanged to the next
  TEST window. Only TEST-window trades are reported as out-of-sample (OOS).
* Objective on train: t-statistic of net R per trade (mean / sd * sqrt(n)), min trade count.
* Realistic sequential simulation: one position per symbol, limit/market entries, partial TPs,
  fees + slippage + real historical funding.
"""
from __future__ import annotations

import itertools
import json
import time
from dataclasses import replace

import numpy as np
import pandas as pd

from . import cfe, dataset as ds, engine, sim

HTF_W = {"15m": 1.0, "1h": 1.5, "4h": 2.0, "1d": 2.0}

GRID = dict(
    htf_set=["base", "base+1d"],
    htf_min=[0.5, 1.0],
    entry_mode=[1, 0],
    exit=["P050", "P333", "P3TR"],
    min_score=[0.0, 60.0, 70.0],
    session=[False, True],
)

FINAL_WEIGHTS = dict(trend=45, struct=15, volume=10, momentum=10, liquidity=10, volatility=10, room=0)


def htf_lists(tf):
    if tf == "5m":
        base = ("15m", "1h", "4h")
    elif tf == "15m":
        base = ("1h", "4h")
    else:
        base = ("4h",)
    return {"base": base, "base+1d": base + ("1d",)}


def windows(train_months=12, test_months=6, first_test="2023-01", last="2026-10"):
    out = []
    t0 = pd.Period(first_test, "M")
    end = pd.Period(last, "M")
    while t0 <= end:
        tr_s = t0 - train_months
        te_e = min(t0 + test_months - 1, end)
        out.append(dict(train=(str(tr_s), str(t0 - 1)), test=(str(t0), str(te_e))))
        t0 = t0 + test_months
    return out


def month_bounds(open_time_ms: np.ndarray, start: str, end: str, bar_ms: int):
    """Bar index range [a, b) whose signal bar CLOSES within months start..end inclusive."""
    s = pd.Period(start, "M").start_time.tz_localize("UTC").value // 10**6
    e = (pd.Period(end, "M") + 1).start_time.tz_localize("UTC").value // 10**6
    close = open_time_ms + bar_ms
    a = int(np.searchsorted(close, s, side="left"))
    b = int(np.searchsorted(close, e, side="left"))
    return a, b


def run_config(R, fund, cfg, p: cfe.P2, a, b):
    """Sequential sim of one config on bars [a,b) using precomputed arrays R."""
    tp1, tp2, tp3, f1, f2, be, lk, tr = ds.EXITS[cfg["exit"]]
    sig = np.zeros(len(R["c"]), np.int8)
    for d, key in ((1, "l"), (-1, "s")):
        m = (R[f"trig_{key}"] & R[f"ok_{key}"] & (R["htf_align"] * d >= cfg["htf_min"] - 1e-9)
             & (R[f"score_{key}"] >= cfg["min_score"]))
        if cfg["session"]:
            m &= R["in_session"]
        if cfg.get("lowvol", False):
            m &= R["lowvol"]
        sig[m] = d
    lv = {}
    for key in ("l", "s"):
        d = 1 if key == "l" else -1
        e = R[f"entry_{key}"] if cfg["entry_mode"] == 1 else R["c"]
        dist = np.abs(e - R[f"sl_{key}"])
        lv[key] = (e, R[f"sl_{key}"], e + d * tp1 * dist, e + d * tp2 * dist, e + d * tp3 * dist)
    T = sim.run_sequential_v2(sig, *lv["l"], *lv["s"], cfg["entry_mode"], p.valid_bars,
                              R["o"], R["h"], R["l"], R["c"], R["atr"], fund, a, b,
                              f1, f2, be, lk, tr, 0, p.fee_taker, p.fee_maker, p.slippage, False)
    return T


def prepare(symbol, tf, df5, fd, htf_set_name, p: cfe.P2):
    hl = htf_lists(tf)[htf_set_name]
    pp = replace(p, htf_list=hl, htf_weights=tuple(HTF_W[x] for x in hl), htf_min=-9.0, min_score=0.0,
                 weights=FINAL_WEIGHTS, session_filter=False)
    dfc = ds.chart(df5, tf)
    R = cfe.compute(dfc, pp, base_df=df5, chart_tf=tf)
    bar_ms = engine.TF_MS[tf]
    hour_close = (((R["open_time"] + bar_ms - 1) // 3_600_000) % 24)
    R["in_session"] = (hour_close >= p.session_start_utc) & (hour_close < p.session_end_utc)
    fund = sim.funding_to_bars(R["open_time"], fd, bar_ms)
    keep = {k: R[k] for k in ("o", "h", "l", "c", "atr", "htf_align", "open_time", "in_session", "lowvol",
                              "trig_l", "ok_l", "score_l", "entry_l", "sl_l",
                              "trig_s", "ok_s", "score_s", "entry_s", "sl_s")}
    return keep, fund


def tstat(r):
    if len(r) < 2:
        return -1e9
    sd = r.std(ddof=1)
    return r.mean() / sd * np.sqrt(len(r)) if sd > 0 else -1e9


def walk_forward(tf="5m", symbols=None, p: cfe.P2 | None = None, min_train_trades=150, log=print):
    symbols = symbols or ds.SYMBOLS
    p = p or cfe.P2()
    wins = windows()
    configs = [dict(zip(GRID.keys(), vals)) for vals in itertools.product(*GRID.values())]
    bar_ms = engine.TF_MS[tf]
    # results[(window_idx, phase, cfg_idx)] -> list of trade arrays
    train_r = {}
    test_trades = {}
    for sym in symbols:
        t0 = time.time()
        df5, fd = ds.load(sym)
        for hs in GRID["htf_set"]:
            R, fund = prepare(sym, tf, df5, fd, hs, p)
            ot = R["open_time"]
            for wi, w in enumerate(wins):
                a_tr, b_tr = month_bounds(ot, *w["train"], bar_ms)
                a_te, b_te = month_bounds(ot, *w["test"], bar_ms)
                for ci, cfg in enumerate(configs):
                    if cfg["htf_set"] != hs:
                        continue
                    if b_tr > a_tr:
                        T = run_config(R, fund, cfg, p, a_tr, b_tr)
                        train_r.setdefault((wi, ci), []).append(T[:, 4].copy())
                    if b_te > a_te:
                        T = run_config(R, fund, cfg, p, a_te, b_te)
                        df = sim.trades_v2(T, ot, bar_ms)
                        df["symbol"] = sym
                        test_trades.setdefault((wi, ci), []).append(df)
            del R
        log(f"{sym} {tf} done in {time.time() - t0:.0f}s")
    # choose per window
    chosen = []
    oos = []
    for wi, w in enumerate(wins):
        best, best_ci, best_stats = -1e18, None, None
        for ci, cfg in enumerate(configs):
            parts = train_r.get((wi, ci), [])
            r = np.concatenate(parts) if parts else np.array([])
            if len(r) < min_train_trades:
                continue
            ts = tstat(r)
            if ts > best:
                best, best_ci, best_stats = ts, ci, dict(n=int(len(r)), mean_r=float(r.mean()), tstat=float(ts))
        if best_ci is None:
            continue
        cfg = configs[best_ci]
        te = pd.concat(test_trades.get((wi, best_ci), [pd.DataFrame()]), ignore_index=True)
        te["window"] = wi
        oos.append(te)
        chosen.append(dict(window=wi, train=w["train"], test=w["test"], cfg=cfg, train_stats=best_stats,
                           test_n=int(len(te)), test_mean_r=float(te["r_net"].mean()) if len(te) else float("nan")))
    oos_df = pd.concat(oos, ignore_index=True) if oos else pd.DataFrame()
    # also keep full grid OOS for every config (to show the distribution / robustness)
    grid_oos = []
    for ci, cfg in enumerate(configs):
        rs = []
        for wi in range(len(wins)):
            parts = test_trades.get((wi, ci), [])
            if parts:
                rs.append(pd.concat(parts, ignore_index=True)["r_net"].to_numpy())
        r = np.concatenate(rs) if rs else np.array([])
        grid_oos.append(dict(cfg_idx=ci, **cfg, n=int(len(r)), mean_r=float(r.mean()) if len(r) else np.nan,
                             total_r=float(r.sum()) if len(r) else 0.0))
    return chosen, oos_df, pd.DataFrame(grid_oos), configs, test_trades


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    chosen, oos, grid, configs, _ = walk_forward(a.tf)
    oos.to_parquet(f"{a.out}/wf_oos_trades_{a.tf}.parquet")
    grid.to_csv(f"{a.out}/wf_grid_oos_{a.tf}.csv", index=False)
    with open(f"{a.out}/wf_chosen_{a.tf}.json", "w") as f:
        json.dump(chosen, f, indent=2, default=str)
    print(json.dumps(chosen, indent=1, default=str))
