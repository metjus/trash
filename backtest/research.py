"""
Candidate-level research: build a dataset of every trigger event with its score components
and the outcome of the trade if it had been taken in isolation (net of fees, slippage and
real funding). Used to (1) measure which layers carry predictive value and (2) calibrate
score thresholds. Only the DESIGN period is used for feature/weight decisions.
"""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
import pandas as pd

from . import data, engine, sim

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT"]
START, END = "2022-01", "2026-10"


def load(symbol: str):
    df = data.load_klines(symbol, "5m", START, END)
    fd = data.load_funding(symbol, START, END)
    return df, fd


def chart_frame(df5: pd.DataFrame, tf: str) -> pd.DataFrame:
    return df5 if tf == "5m" else engine.resample(df5, tf)


def candidates(symbol: str, tf: str, p: engine.Params, df5=None, fd=None, loose: bool = True) -> pd.DataFrame:
    """All trigger events (both directions) with components + independent outcomes."""
    if df5 is None:
        df5, fd = load(symbol)
    dfc = chart_frame(df5, tf)
    pp = p
    if loose:
        pp = replace(p, min_score=0.0, cost_mult=0.0, room_min_r=-1e9, htf_veto=-9.0, vol_rank_max=101.0)
    R = engine.compute(dfc, pp, base_df=df5, chart_tf=tf)
    bar_ms = engine.TF_MS[tf]
    fund = sim.funding_to_bars(R["open_time"], fd, bar_ms)
    rows = []
    for d, key in ((1, "l"), (-1, "s")):
        m = R[f"cand_{key}"]
        idx = np.nonzero(m)[0]
        if len(idx) == 0:
            continue
        comp = R[f"comp_{key}"]
        frame = pd.DataFrame({"i": idx, "dir": d, "trigger": R[f"trig_{key}"][idx], "score": R[f"score_{key}"][idx]})
        for k, v in comp.items():
            frame[k] = v[idx]
        frame["entry"] = R["c"][idx]
        frame["sl"] = R[f"sl_{key}"][idx]
        frame["tp1"] = R[f"tp1_{key}"][idx]; frame["tp2"] = R[f"tp2_{key}"][idx]; frame["tp3"] = R[f"tp3_{key}"][idx]
        frame["risk_pct"] = np.abs(frame["entry"] - frame["sl"]) / frame["entry"] * 100
        frame["atr_pct"] = R["atr"][idx] / R["c"][idx] * 100
        frame["atr_rank"] = R["atr_rank"][idx]
        frame["rvol"] = R["rvol"][idx]
        frame["pressure"] = R["pressure"][idx] * d
        frame["align"] = R["align"][idx] * d
        frame["htf_align"] = R["htf_align"][idx] * d
        frame["t_local"] = R["t_local"][idx] * d
        frame["room"] = R[f"room_{key}"][idx]
        frame["rsi_d"] = R["rsi"][idx] if d == 1 else 100 - R["rsi"][idx]
        frame["ms_d"] = R["ms"][idx] * d
        rows.append(frame)
    if not rows:
        return pd.DataFrame()
    cdf = pd.concat(rows, ignore_index=True).sort_values("i").reset_index(drop=True)
    exit_l = R["bear_break"] > 0
    exit_s = R["bull_break"] > 0
    out = sim.run_independent(cdf["i"].to_numpy(np.int64), cdf["dir"].to_numpy(np.int8),
                              cdf["entry"].to_numpy(), cdf["sl"].to_numpy(), cdf["tp1"].to_numpy(),
                              cdf["tp2"].to_numpy(), cdf["tp3"].to_numpy(),
                              R["o"], R["h"], R["l"], R["c"], R["atr"], fund, exit_l, exit_s,
                              p.frac_tp1, p.frac_tp2, p.be_after_tp1, p.lock_after_tp2, p.trail_atr, p.max_bars,
                              p.fee_taker, p.fee_maker, p.slippage, p.tp_as_maker, p.exit_on_choch)
    cdf["r_net"], cdf["exit_i"], cdf["reason"], cdf["stage"], cdf["r_cost"], cdf["r_fund"] = out
    cdf["r_gross"] = cdf["r_net"] + cdf["r_cost"] + cdf["r_fund"]
    cdf["time"] = pd.to_datetime(R["open_time"][cdf["i"].to_numpy()] + bar_ms, unit="ms", utc=True)
    cdf["symbol"] = symbol
    cdf["tf"] = tf
    return cdf
