"""Setup-level dataset for score calibration and walk-forward analysis (CFE v2)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import cfe, data, engine, sim

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT"]
START, END = "2022-01", "2026-10"


def load(symbol):
    return data.load_klines(symbol, "5m", START, END), data.load_funding(symbol, START, END)


def chart(df5, tf):
    return df5 if tf == "5m" else engine.resample(df5, tf)


EXITS = {
    # name: (tp1R, tp2R, tp3R, frac1, frac2, be_after_tp1, lock_after_tp2, trail_atr)
    "P333": (1.0, 2.0, 3.0, 1 / 3, 1 / 3, True, True, 0.0),     # partials 1/3 each, BE after TP1
    "P050": (1.0, 2.0, 3.0, 0.0, 1.0, False, False, 0.0),        # 100% at TP2 (2R), TP1/TP3 informational
    "P3TR": (1.0, 2.0, 20.0, 1 / 3, 1 / 3, True, True, 3.0),     # 1/3 at 1R, 1/3 at 2R, runner trailed 3 ATR
    "P2NB": (1.0, 2.0, 3.0, 0.5, 0.5, False, False, 0.0),        # 50% at 1R, 50% at 2R, no BE
}


def setups(symbol: str, tf: str, p: cfe.P2, df5=None, fd=None, modes=(1, 0), exits=("P333", "P050"),
           end_time=None) -> pd.DataFrame:
    """All setups (context filter relaxed so it can be studied) with features and outcomes."""
    if df5 is None:
        df5, fd = load(symbol)
    if end_time is not None:
        df5 = df5[df5["time"] < end_time].reset_index(drop=True)
    dfc = chart(df5, tf)
    pl = replace(p, htf_min=-9.0, min_score=0.0)
    R = cfe.compute(dfc, pl, base_df=df5, chart_tf=tf)
    bar_ms = engine.TF_MS[tf]
    fund = sim.funding_to_bars(R["open_time"], fd, bar_ms)
    frames = []
    for d, key in ((1, "l"), (-1, "s")):
        idx = np.nonzero(R[f"setup_{key}"])[0]
        if len(idx) == 0:
            continue
        base = pd.DataFrame({"i": idx, "dir": d})
        for k, v in R[f"F_{key}"].items():
            base[k] = v[idx]
        comps = cfe.score_components(R[f"F_{key}"])
        for k, v in comps.items():
            base["c_" + k] = v[idx]
        base["risk_pct"] = R[f"dist_{key}"][idx] / R[f"entry_{key}"][idx] * 100
        base["time"] = pd.to_datetime(R["open_time"][idx] + bar_ms, unit="ms", utc=True)
        base["hour"] = R["hour"][idx]
        for mode in modes:
            entry = R[f"entry_{key}"][idx] if mode == 1 else R["c"][idx]
            sl = R[f"sl_{key}"][idx]
            dist = np.abs(entry - sl)
            for ex in exits:
                a, b, cc, f1, f2, be, lk, tr = EXITS[ex]
                out = sim.run_independent_v2(idx.astype(np.int64), np.full(len(idx), d, np.int8), entry, sl,
                                             entry + d * a * dist, entry + d * b * dist, entry + d * cc * dist,
                                             mode, p.valid_bars, R["o"], R["h"], R["l"], R["c"], R["atr"], fund,
                                             f1, f2, be, lk, tr, 0, p.fee_taker, p.fee_maker, p.slippage)
                X = base.copy()
                X["mode"] = mode
                X["exit"] = ex
                X["filled"] = out[:, 0]
                X["r_net"] = out[:, 1]; X["r_gross"] = out[:, 2]; X["r_cost"] = out[:, 3]; X["r_fund"] = out[:, 4]
                X["bars"] = out[:, 5]
                frames.append(X)
    if not frames:
        return pd.DataFrame()
    A = pd.concat(frames, ignore_index=True)
    A["symbol"] = symbol
    A["tf"] = tf
    return A
