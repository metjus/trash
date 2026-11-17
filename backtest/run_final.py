"""
Produce every number used in docs/03_validation_report.md.

    PYTHONPATH=. CFE_DATA_DIR=<cache> python -m backtest.run_final --wf <walk-forward output dir> --out results
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import cfe, dataset as ds, engine, evaluate as ev, sim, walkforward as wf

BUCKETS = [(-1, 50, "NO TRADE (<50)"), (50, 65, "WEAK (50-64)"), (65, 80, "VALID (65-79)"),
           (80, 90, "STRONG (80-89)"), (90, 101, "HIGH-CONVICTION (90+)")]


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main(wf_dir: str, out: str):
    os.makedirs(out, exist_ok=True)
    res = {}

    # ---------------- 1. walk-forward summary ----------------
    for tf in ("5m", "15m"):
        oos = pd.read_parquet(f"{wf_dir}/wf_oos_trades_{tf}.parquet")
        chosen = json.load(open(f"{wf_dir}/wf_chosen_{tf}.json"))
        grid = pd.read_csv(f"{wf_dir}/wf_grid_oos_{tf}.csv")
        bm = 5 if tf == "5m" else 15
        res[f"wf_{tf}_all"] = ev.summarize(oos, bar_minutes=bm)
        res[f"wf_{tf}_true_oos"] = ev.summarize(oos[oos["entry_time"] >= "2023-07-01"], bar_minutes=bm)
        rows = []
        for c in chosen:
            cfg = c["cfg"]
            rows.append(dict(test=f'{c["test"][0]}..{c["test"][1]}', train=f'{c["train"][0]}..{c["train"][1]}',
                             config=f'HTF={cfg["htf_set"]} min={cfg["htf_min"]} {"limit" if cfg["entry_mode"] == 1 else "market"} '
                                    f'{cfg["exit"]} score>={int(cfg["min_score"])} session={"on" if cfg["session"] else "off"}',
                             train_trades=c["train_stats"]["n"], train_avg_R=round(c["train_stats"]["mean_r"], 3),
                             test_trades=c["test_n"], test_avg_R=round(c["test_mean_r"], 3)))
        pd.DataFrame(rows).to_csv(f"{out}/wf_windows_{tf}.csv", index=False)
        res[f"wf_{tf}_windows_md"] = md(pd.DataFrame(rows))
        dims = {}
        for dim in ["htf_set", "htf_min", "entry_mode", "exit", "min_score", "session"]:
            dims[dim] = grid.groupby(dim).apply(lambda x: round(float(np.average(x.mean_r, weights=x.n)), 4), include_groups=False).to_dict()
        res[f"wf_{tf}_marginals"] = {k: {str(a): b for a, b in v.items()} for k, v in dims.items()}
        res[f"wf_{tf}_grid_range"] = dict(min=round(float(grid.mean_r.min()), 3), median=round(float(grid.mean_r.median()), 3),
                                          max=round(float(grid.mean_r.max()), 3), n_configs=int(len(grid)),
                                          n_positive=int((grid.mean_r > 0).sum()))
        oos.to_csv(f"{out}/wf_oos_trades_{tf}.csv", index=False)

    # ---------------- 2. pre-registered config ----------------
    all_hold = {}
    for tf in ("5m", "15m"):
        bm = 5 if tf == "5m" else 15
        frames_wf, frames_ho = [], []
        for sym in ds.SYMBOLS:
            frames_wf.append(ev.trades_for(sym, tf, start="2023-07", end="2026-10"))
        for sym in ev.HOLDOUT:
            frames_ho.append(ev.trades_for(sym, tf, start="2022-01", end="2026-10"))
        twf = pd.concat(frames_wf, ignore_index=True)
        tho = pd.concat(frames_ho, ignore_index=True)
        all_hold[tf] = tho
        res[f"pre_{tf}_wf_symbols_2023H2plus"] = ev.summarize(twf, bar_minutes=bm)
        res[f"pre_{tf}_holdout"] = ev.summarize(tho, bar_minutes=bm)
        tho.to_csv(f"{out}/holdout_trades_{tf}.csv", index=False)
        # per symbol / per year / regime
        res[f"pre_{tf}_holdout_by_symbol_md"] = md(pd.DataFrame([dict(symbol=s, **{k: v for k, v in ev.summarize(g, bar_minutes=bm).items() if k in ("trades", "win_rate_pct", "avg_R_net", "profit_factor", "total_R", "max_dd_pct")}) for s, g in tho.groupby("symbol")]))
        res[f"pre_{tf}_holdout_by_year_md"] = md(pd.DataFrame([dict(year=int(y), **{k: v for k, v in ev.summarize(g, bar_minutes=bm).items() if k in ("trades", "win_rate_pct", "avg_R_net", "avg_R_gross", "profit_factor", "total_R", "long_avg_R", "short_avg_R")}) for y, g in tho.groupby(tho["entry_time"].dt.year)]))
        res[f"pre_{tf}_holdout_regime_md"] = md(ev.regime_table(tho))
        both = pd.concat([twf, tho], ignore_index=True)
        res[f"pre_{tf}_combined_regime_md"] = md(ev.regime_table(both))
        res[f"pre_{tf}_exit_reasons"] = tho["reason"].value_counts().to_dict()

        # cost sensitivity on holdout
        rows = []
        for name, (ft, fm, sl) in {"Binance VIP0 (0.05/0.02 + 0.02 slip)": (0.05, 0.02, 0.02),
                                   "Reduced (0.04/0.016 + 0.01 slip)": (0.04, 0.016, 0.01),
                                   "Low (0.02/0.0 + 0.01 slip)": (0.02, 0.0, 0.01),
                                   "Zero costs (gross)": (0.0, 0.0, 0.0)}.items():
            fr = []
            for sym in ev.HOLDOUT:
                p = cfe.P2(fee_taker=ft, fee_maker=fm, slippage=sl)
                fr.append(ev.trades_for(sym, tf, start="2022-01", end="2026-10", p=p))
            s = ev.summarize(pd.concat(fr, ignore_index=True), bar_minutes=bm)
            rows.append(dict(costs=name, trades=s["trades"], avg_R_net=s["avg_R_net"], profit_factor=s["profit_factor"],
                             total_R=s["total_R"], t_stat=s["t_stat"], max_dd_pct=s["max_dd_pct"]))
        res[f"pre_{tf}_cost_sensitivity_md"] = md(pd.DataFrame(rows))

        # equity curve (0.5 % risk per trade, trades in time order across holdout symbols)
        t = tho.sort_values("entry_time")
        eq = np.cumprod(1 + 0.005 * t["r_net"].to_numpy())
        eqg = np.cumprod(1 + 0.005 * t["r_gross"].to_numpy())
        fig, ax = plt.subplots(figsize=(10, 4.2), dpi=110)
        ax.plot(t["entry_time"], eqg, color="#9aa0a6", lw=1.2, label="before costs (gross)")
        ax.plot(t["entry_time"], eq, color="#1a73e8", lw=1.6, label="after fees + slippage + funding")
        ax.axhline(1.0, color="#5f6368", lw=0.8, ls="--")
        ax.set_title(f"CFE default config – holdout symbols (never used in design), {tf} chart, 0.5% risk/trade")
        ax.set_ylabel("equity (start = 1.0)")
        ax.legend(frameon=False)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(f"{out}/equity_holdout_{tf}.png")
        plt.close(fig)

    # ---------------- 3. score buckets (independent outcomes, holdout, default filters) ----------------
    for tf in ("5m", "15m"):
        rows = []
        frames = []
        for sym in ev.HOLDOUT:
            p = cfe.P2(weights=wf.FINAL_WEIGHTS, htf_list=wf.htf_lists(tf)["base"],
                       htf_weights=tuple(wf.HTF_W[x] for x in wf.htf_lists(tf)["base"]), session_filter=True)
            A = ds.setups(sym, tf, p, modes=(1,), exits=("P333",))
            A = A[(A["htf_align"] >= 1.0 - 1e-9) & (A["filled"] == 1)]
            frames.append(A)
        A = pd.concat(frames, ignore_index=True)
        # score column: recompute from stored components with the final weights
        comps = {k[2:]: A[k].to_numpy() for k in A.columns if k.startswith("c_")}
        num = sum(wf.FINAL_WEIGHTS[k] * comps[k] for k in wf.FINAL_WEIGHTS if wf.FINAL_WEIGHTS[k] > 0)
        den = sum(w for w in wf.FINAL_WEIGHTS.values() if w > 0)
        A["score"] = 100 * num / den
        for lo, hi, name in BUCKETS:
            g = A[(A["score"] >= lo) & (A["score"] < hi)]
            if len(g) == 0:
                rows.append(dict(bucket=name, setups=0))
                continue
            r = g["r_net"].to_numpy()
            rows.append(dict(bucket=name, setups=int(len(g)), win_rate_pct=round(float((r > 0).mean() * 100), 1),
                             avg_R_net=round(float(r.mean()), 3), avg_R_gross=round(float(g["r_gross"].mean()), 3),
                             t_stat=round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2) if len(r) > 2 else np.nan))
        res[f"score_buckets_{tf}_md"] = md(pd.DataFrame(rows))
        # Spearman correlation score vs outcome
        res[f"score_rank_corr_{tf}"] = round(float(pd.Series(A["score"]).corr(pd.Series(A["r_net"]), method="spearman")), 4)

    # ---------------- 4. delta estimate quality ----------------
    res["delta_estimate_quality_BTC_2024"] = ev.delta_estimate_quality("BTCUSDT")
    res["delta_estimate_quality_SOL_2024"] = ev.delta_estimate_quality("SOLUSDT")

    with open(f"{out}/final_results.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    for k, v in res.items():
        if isinstance(v, str):
            print(f"\n### {k}\n{v}")
        else:
            print(f"\n### {k}\n{json.dumps(v, default=str)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wf", required=True)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    main(a.wf, a.out)
