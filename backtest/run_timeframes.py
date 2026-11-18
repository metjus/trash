"""Exploratory (NOT pre-registered) test of the default configuration on other chart timeframes, using the same
'Auto' higher-timeframe rule as the Pine indicator. Holdout-1 symbols, 2022-01 .. 2026-10.

    PYTHONPATH=. CFE_DATA_DIR=<cache> python -m backtest.run_timeframes --out results
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from . import cfe, dataset as ds, engine, evaluate as ev, sim, walkforward as wf

# Pine 'Auto' rule: chart < 15m -> 15m/1h/4h (w 1/1.5/2); chart >= 15m -> next two of 1h/4h/1D/1W (w 1.5/2)
AUTO = {"5m": (("15m", "1h", "4h"), (1.0, 1.5, 2.0)), "15m": (("1h", "4h"), (1.5, 2.0)), "30m": (("1h", "4h"), (1.5, 2.0)),
        "1h": (("4h", "1d"), (1.5, 2.0)), "4h": (("1d", "1w"), (1.5, 2.0))}
MINUTES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}


def run(tf, symbols):
    hl, w = AUTO[tf]
    high_tf = engine.TF_MS[tf] >= engine.TF_MS["4h"]
    p = cfe.P2(htf_list=hl, htf_weights=w, htf_min=1.0, min_score=70.0, weights=wf.FINAL_WEIGHTS, entry_mode=1,
               session_filter=not high_tf, atr_rank_len=200 if high_tf else 500)
    a, b_, c, f1, f2, be, lk, tr = ds.EXITS["P333"]
    frames = []
    for sym in symbols:
        df5, fd = ds.load(sym)
        dfc = ds.chart(df5, tf)
        R = cfe.compute(dfc, p, base_df=df5, chart_tf=tf)
        bar_ms = engine.TF_MS[tf]
        fund = sim.funding_to_bars(R["open_time"], fd, bar_ms)
        sig = np.where(R["sig_l"], 1, np.where(R["sig_s"], -1, 0)).astype(np.int8)
        lv = {}
        for key, d in (("l", 1), ("s", -1)):
            e = R[f"entry_{key}"]; dist = np.abs(e - R[f"sl_{key}"])
            lv[key] = (e, R[f"sl_{key}"], e + d * a * dist, e + d * b_ * dist, e + d * c * dist)
        T = sim.run_sequential_v2(sig, *lv["l"], *lv["s"], 1, p.valid_bars, R["o"], R["h"], R["l"], R["c"], R["atr"], fund,
                                  0, len(R["c"]), f1, f2, be, lk, tr, 0, p.fee_taker, p.fee_maker, p.slippage, False)
        t = sim.trades_v2(T, R["open_time"], bar_ms); t["symbol"] = sym
        frames.append(t)
    T = pd.concat(frames, ignore_index=True)
    s = ev.summarize(T, bar_minutes=MINUTES[tf])
    months = 58
    s["signals_per_month_per_pair"] = round(s["trades"] / months / len(symbols), 2) if s["trades"] else 0.0
    s["htf"] = "+".join(hl)
    return s


def main(out):
    res = {tf: run(tf, ev.HOLDOUT) for tf in ("5m", "15m", "30m", "1h", "4h")}
    with open(f"{out}/timeframes_holdout1.json", "w") as f:
        json.dump(res, f, indent=2)
    rows = [dict(tf=tf, htf=r["htf"], trades=r["trades"], per_month_pair=r["signals_per_month_per_pair"], win=r["win_rate_pct"],
                 gross=r["avg_R_gross"], cost=round(r["avg_cost_R"] + r["avg_funding_R"], 3), net=r["avg_R_net"], pf=r["profit_factor"],
                 t=r["t_stat"], hold_h=r["avg_hold_h"]) for tf, r in res.items()]
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="results")
    main(ap.parse_args().out)
