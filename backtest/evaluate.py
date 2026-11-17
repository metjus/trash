"""
Final evaluation of the PRE-REGISTERED default configuration (chosen from walk-forward marginal
effects BEFORE looking at the holdout symbols), plus breakdowns used in the validation report.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import cfe, data, dataset as ds, engine, sim, walkforward as wf

HOLDOUT = ["ADAUSDT", "LTCUSDT", "DOTUSDT", "ATOMUSDT", "NEARUSDT", "FILUSDT", "TRXUSDT", "ETCUSDT"]

# Pre-registered default (identical to the Pine defaults)
DEFAULT_CFG = dict(htf_set="base", htf_min=1.0, entry_mode=1, exit="P333", min_score=70.0, session=True)


def trades_for(symbol, tf, cfg=DEFAULT_CFG, start="2022-01", end="2026-10", p: cfe.P2 | None = None, df5=None, fd=None):
    p = p or cfe.P2()
    if df5 is None:
        df5, fd = ds.load(symbol)
    R, fund = wf.prepare(symbol, tf, df5, fd, cfg["htf_set"], p)
    bar_ms = engine.TF_MS[tf]
    a, b = wf.month_bounds(R["open_time"], start, end, bar_ms)
    T = wf.run_config(R, fund, cfg, p, a, b)
    df = sim.trades_v2(T, R["open_time"], bar_ms)
    df["symbol"] = symbol
    df["tf"] = tf
    # attach regime info (trailing 30d return and 30d realised vol at the signal bar)
    c = R["c"]
    bars30 = int(30 * 86_400_000 / bar_ms)
    sig = df["sig_bar"].to_numpy()
    prev = np.clip(sig - bars30, 0, None)
    df["ret30"] = c[sig] / c[prev] - 1.0
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    vol = pd.Series(lr).rolling(bars30, min_periods=bars30 // 2).std().to_numpy() * np.sqrt(365 * 86_400_000 / bar_ms)
    df["vol30"] = vol[sig]
    df["vol_med"] = np.nanmedian(vol)
    return df


def summarize(tr: pd.DataFrame, risk_pct=0.5, bar_minutes=5) -> dict:
    if len(tr) == 0:
        return dict(trades=0)
    tr = tr.sort_values("entry_time")
    r = tr["r_net"].to_numpy()
    g = tr["r_gross"].to_numpy()
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    eq = np.cumprod(1.0 + risk_pct / 100.0 * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    sd = r.std(ddof=1) if len(r) > 1 else np.nan
    return dict(
        trades=int(len(r)),
        win_rate_pct=round(float((r > 0).mean() * 100), 1),
        avg_R_net=round(float(r.mean()), 3),
        avg_R_gross=round(float(g.mean()), 3),
        avg_cost_R=round(float(tr["r_cost"].mean()), 3),
        avg_funding_R=round(float(tr["r_fund"].mean()), 4),
        profit_factor=round(float(wins / losses), 2) if losses > 0 else float("inf"),
        total_R=round(float(r.sum()), 1),
        t_stat=round(float(r.mean() / sd * np.sqrt(len(r))), 2) if sd and sd > 0 else np.nan,
        net_profit_pct=round(float((eq[-1] - 1) * 100), 1),
        max_dd_pct=round(float((eq / peak - 1).min() * 100), 1),
        avg_win_R=round(float(r[r > 0].mean()), 2) if (r > 0).any() else 0.0,
        avg_loss_R=round(float(r[r <= 0].mean()), 2) if (r <= 0).any() else 0.0,
        avg_hold_h=round(float(tr["bars"].mean() * bar_minutes / 60), 1),
        long_n=int((tr["dir"] == 1).sum()), long_avg_R=round(float(tr.loc[tr["dir"] == 1, "r_net"].mean()), 3) if (tr["dir"] == 1).any() else np.nan,
        short_n=int((tr["dir"] == -1).sum()), short_avg_R=round(float(tr.loc[tr["dir"] == -1, "r_net"].mean()), 3) if (tr["dir"] == -1).any() else np.nan,
    )


def regime_table(tr: pd.DataFrame) -> pd.DataFrame:
    t = tr.copy()
    t["trend_regime"] = np.where(t["ret30"] > 0.15, "Bull (30d > +15%)", np.where(t["ret30"] < -0.15, "Bear (30d < -15%)", "Sideways"))
    t["vol_regime"] = np.where(t["vol30"] > t["vol_med"], "High volatility", "Low volatility")
    rows = []
    for col in ("trend_regime", "vol_regime"):
        for k, g in t.groupby(col):
            s = summarize(g)
            rows.append(dict(regime=k, trades=s["trades"], win_rate_pct=s["win_rate_pct"], avg_R_net=s["avg_R_net"],
                             avg_R_gross=s["avg_R_gross"], profit_factor=s["profit_factor"], total_R=s["total_R"],
                             long_avg_R=s["long_avg_R"], short_avg_R=s["short_avg_R"]))
    return pd.DataFrame(rows)


def delta_estimate_quality(symbol="BTCUSDT", start="2024-01-01", end="2025-01-01"):
    """How well does the OHLC-based buy/sell estimate track the REAL taker delta (Binance)?"""
    df, _ = ds.load(symbol)
    df = df[(df["time"] >= start) & (df["time"] < end)]
    h, l, c, v = (df[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
    rng = h - l
    clv = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1), 0.5)
    est = v * (2 * clv - 1)
    real = 2 * df["taker_buy_volume"].to_numpy(float) - v
    out = dict(bars=len(df), corr_bar=float(np.corrcoef(est, real)[0, 1]),
               sign_agreement_pct=float((np.sign(est) == np.sign(real)).mean() * 100))
    for n in (10, 50):
        e = pd.Series(est).rolling(n).sum(); r = pd.Series(real).rolling(n).sum(); vv = pd.Series(v).rolling(n).sum()
        out[f"corr_pressure_{n}"] = float((e / vv).corr(r / vv))
    return out
