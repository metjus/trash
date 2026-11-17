"""
No-look-ahead / non-repainting test of the reference engine.

For several random cut points t, the engine is run on data truncated at t and on the full data.
Every value the signal logic uses for bars < t (setups, entry/SL/TP levels, scores, HTF alignment)
must be IDENTICAL. Any use of future data would make them differ.

    PYTHONPATH=. CFE_DATA_DIR=<cache> python -m pytest -q tests/test_no_lookahead.py
"""
import os

import numpy as np
import pytest

from backtest import cfe, dataset as ds, walkforward as wf

KEYS = ["setup_l", "setup_s", "sig_l", "sig_s", "entry_l", "sl_l", "tp1_l", "tp2_l", "tp3_l",
        "entry_s", "sl_s", "tp1_s", "tp2_s", "tp3_s", "score_l", "score_s", "htf_align", "ms",
        "bull_break", "bear_break", "up1", "dn1", "atr_rank"]


def _cmp(a, b):
    a = np.asarray(a); b = np.asarray(b)
    if a.dtype == bool or b.dtype == bool or a.dtype.kind in "iu":
        return np.array_equal(a, b)
    return np.allclose(a, b, equal_nan=True, rtol=0, atol=1e-9)


@pytest.mark.parametrize("tf", ["5m", "15m"])
def test_truncation_invariance(tf):
    if not os.environ.get("CFE_DATA_DIR"):
        pytest.skip("set CFE_DATA_DIR to the data cache")
    df5, _ = ds.load("BTCUSDT")
    df5 = df5[(df5["time"] >= "2024-01-01") & (df5["time"] < "2024-04-01")].reset_index(drop=True)
    hl = wf.htf_lists(tf)["base"]
    p = cfe.P2(htf_list=hl, htf_weights=tuple(wf.HTF_W[x] for x in hl), htf_min=1.0, min_score=70.0,
               weights=wf.FINAL_WEIGHTS)
    full_c = ds.chart(df5, tf)
    R_full = cfe.compute(full_c, p, base_df=df5, chart_tf=tf)
    rng = np.random.default_rng(7)
    n = len(full_c)
    for cut in rng.integers(n // 3, n - 10, size=6):
        cut_time = full_c["open_time"].iloc[cut]
        base_cut = df5[df5["open_time"] < cut_time].reset_index(drop=True)
        c_cut = ds.chart(base_cut, tf)
        assert len(c_cut) == cut
        R_cut = cfe.compute(c_cut, p, base_df=base_cut, chart_tf=tf)
        for k in KEYS:
            assert _cmp(R_cut[k], R_full[k][:cut]), f"{k} differs at cut {cut} ({tf}) -> look-ahead!"
