"""
Design-period study (2022-01 .. 2023-06 only) – reproduces the tables in docs/03_validation_report.md §2.

  1. v1 "classic confluence" engine (engine.py): per-trigger outcomes, score deciles and per-layer rank
     correlations with the trade outcome.
  2. v2 setups (cfe.py): HTF alignment threshold x entry mode x exit model.
  3. Score calibration: ridge regression trained on 2022, validated on 2023-H1 (out-of-time).

    PYTHONPATH=. CFE_DATA_DIR=<cache> python -m backtest.design_study --out results
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from . import cfe, dataset as ds, engine, research as rs

DESIGN_END = "2023-07-01"


def v1_study():
    p = engine.Params(exit_on_choch=False)
    frames = []
    for sym in ds.SYMBOLS:
        df5, fd = ds.load(sym)
        df5 = df5[df5["time"] < "2023-09-01"].reset_index(drop=True)
        for tf in ("5m", "15m", "1h"):
            frames.append(rs.candidates(sym, tf, p, df5, fd))
    A = pd.concat(frames, ignore_index=True)
    A = A[A["time"] < DESIGN_END]
    trig = A.groupby(["tf", "trigger"]).agg(n=("r_net", "size"), gross_R=("r_gross", "mean"), cost_R=("r_cost", "mean"),
                                            net_R=("r_net", "mean")).round(3).reset_index()
    trig["trigger"] = trig["trigger"].map({1: "sweep & reclaim", 2: "BOS/CHoCH break", 3: "pullback"})
    dec = []
    for tf in ("5m", "15m", "1h"):
        X = A[A["tf"] == tf]
        q = pd.qcut(X["score"], 10, labels=False, duplicates="drop")
        g = X.assign(q=q).groupby("q").agg(score=("score", "mean"), gross_R=("r_gross", "mean"), net_R=("r_net", "mean"))
        dec.append(dict(tf=tf, **{f"D{int(k) + 1}": f'{r.gross_R:+.3f}' for k, r in g.iterrows()}))
    comps = ["trend", "struct", "volume", "momentum", "liquidity", "volatility", "room", "rvol", "pressure", "rsi_d", "atr_rank", "risk_pct"]
    corr = []
    for tf in ("5m", "15m", "1h"):
        X = A[A["tf"] == tf]
        c = X[comps + ["r_gross"]].corr(method="spearman")["r_gross"].drop("r_gross")
        corr.append(dict(tf=tf, **{k: round(float(v), 3) for k, v in c.items()}))
    return trig, pd.DataFrame(dec), pd.DataFrame(corr)


def v2_study():
    p = cfe.P2(cost_mult=0.0)
    frames = []
    for sym in ds.SYMBOLS:
        df5, fd = ds.load(sym)
        for tf in ("5m", "15m"):
            frames.append(ds.setups(sym, tf, p, df5, fd, modes=(1, 0), exits=("P333", "P050", "P3TR"), end_time="2023-09-01"))
    A = pd.concat(frames, ignore_index=True)
    A = A[(A["time"] < DESIGN_END) & (A["filled"] == 1)]
    rows = []
    for thr in (-9, 0.5, 1.0):
        X = A[A["htf_align"] >= thr - 1e-9]
        g = X.groupby(["tf", "mode", "exit"]).agg(n=("r_net", "size"), gross_R=("r_gross", "mean"), cost_R=("r_cost", "mean"),
                                                   net_R=("r_net", "mean")).reset_index()
        g.insert(0, "htf_min", "none" if thr < -1 else thr)
        rows.append(g)
    T = pd.concat(rows, ignore_index=True).round(3)
    T["mode"] = T["mode"].map({1: "limit retest", 0: "market"})
    # long vs short with full alignment (regime dependence)
    X = A[A["htf_align"] >= 1.0 - 1e-9]
    ls = X.groupby(["tf", "mode", "dir"]).agg(n=("r_net", "size"), gross_R=("r_gross", "mean"), net_R=("r_net", "mean")).round(3).reset_index()
    ls["mode"] = ls["mode"].map({1: "limit retest", 0: "market"})
    ls["dir"] = ls["dir"].map({1: "long", -1: "short"})
    # ridge calibration, train 2022 -> validate 2023H1
    comps = ["c_trend", "c_struct", "c_volume", "c_momentum", "c_liquidity", "c_volatility", "c_room"]
    cal = []
    for tf in ("5m", "15m"):
        for mode, ex in ((1, "P333"), (1, "P050"), (0, "P333")):
            Y = A[(A["tf"] == tf) & (A["mode"] == mode) & (A["exit"] == ex)]
            tr, va = Y[Y["time"] < "2023-01-01"], Y[Y["time"] >= "2023-01-01"]
            M = tr[comps].to_numpy(float); mu, sd = M.mean(0), M.std(0) + 1e-9
            Z = np.column_stack([np.ones(len(M)), (M - mu) / sd])
            I = np.eye(Z.shape[1]); I[0, 0] = 0
            b = np.linalg.solve(Z.T @ Z + 10 * I, Z.T @ tr["r_gross"].to_numpy())
            pv = b[0] + ((va[comps].to_numpy(float) - mu) / sd) @ b[1:]
            rho = pd.Series(pv).corr(pd.Series(va["r_gross"].to_numpy()), method="spearman")
            cal.append(dict(tf=tf, entry="limit" if mode == 1 else "market", exit=ex, train_n=len(tr), valid_n=len(va),
                            valid_rank_corr=round(float(rho), 3), **{f"coef_{c[2:]}": round(float(x), 3) for c, x in zip(comps, b[1:])}))
    return T, ls, pd.DataFrame(cal)


def main(out):
    trig, dec, corr = v1_study()
    T, ls, cal = v2_study()
    res = dict(v1_triggers=trig.to_markdown(index=False), v1_score_deciles_gross=dec.to_markdown(index=False),
               v1_component_rank_corr=corr.to_markdown(index=False), v2_grid=T.to_markdown(index=False),
               v2_long_short_aligned=ls.to_markdown(index=False), v2_ridge_calibration=cal.to_markdown(index=False))
    with open(f"{out}/design_study.json", "w") as f:
        json.dump(res, f, indent=2)
    for k, v in res.items():
        print(f"\n### {k}\n{v}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    main(ap.parse_args().out)
