"""Pre-registered holdout-2 test (see results/PREREGISTRATION_holdout2.md)."""
from __future__ import annotations

import json
import sys

import pandas as pd

from . import cfe, dataset as ds, evaluate as ev

HOLDOUT2 = ["UNIUSDT", "AAVEUSDT", "XLMUSDT", "ALGOUSDT", "SANDUSDT", "AXSUSDT", "EGLDUSDT", "VETUSDT"]


def main(out="results"):
    res = {}
    for tf in ("5m", "15m"):
        bm = 5 if tf == "5m" else 15
        for name, extra in (("A_default", {}), ("B_default_plus_lowvol", {"lowvol": True})):
            cfg = dict(ev.DEFAULT_CFG, **extra)
            frames = []
            for sym in HOLDOUT2:
                frames.append(ev.trades_for(sym, tf, cfg=cfg, start="2022-01", end="2026-10"))
            T = pd.concat(frames, ignore_index=True)
            res[f"{tf}_{name}"] = ev.summarize(T, bar_minutes=bm)
            T.to_csv(f"{out}/holdout2_trades_{tf}_{name}.csv", index=False)
            print(tf, name, json.dumps(res[f"{tf}_{name}"]), flush=True)
    a5, b5 = res["5m_A_default"]["avg_R_net"], res["5m_B_default_plus_lowvol"]["avg_R_net"]
    a15, b15 = res["15m_A_default"]["avg_R_net"], res["15m_B_default_plus_lowvol"]["avg_R_net"]
    res["decision_rule_1_adopt_B"] = bool(b5 > a5 and b15 > a15)
    res["decision_rule_2_positive_expectancy"] = {k: bool(v["avg_R_net"] > 0 and v["t_stat"] >= 2.0) for k, v in res.items() if isinstance(v, dict)}
    with open(f"{out}/holdout2_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k.startswith("decision")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")
