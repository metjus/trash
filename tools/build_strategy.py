"""Build pine/CFE_strategy.pine from the indicator's engine sections + the strategy execution layer.

The engine (inputs, helpers, core series, MTF alignment, structure/liquidity, setup/score) is copied
verbatim so that the indicator and the strategy can never drift apart.
    python tools/build_strategy.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IND = ROOT / "pine" / "CFE_indicator.pine"
OUT = ROOT / "pine" / "CFE_strategy.pine"
PARTS = ROOT / "tools" / "strategy_parts"

DROP_INPUTS = ("tfD1", "tfD2", "tfD3", "tfD4", "tfD5", "tfD6", "useLtf", "lvlWeak", "lvlValid", "lvlStrong", "lvlHigh",
               "showStruct", "showLiq", "showZones", "showSweeps", "showPreview", "showDash", "dashPos", "dashSize",
               "detailLbl", "exitAdvisory", "showLevels", "hcScore", "showScen")


def section(src, title):
    start = None
    for i, l in enumerate(src):
        if l.startswith("// " + title) and src[i - 1].startswith("// ═"):
            start = i - 1
            break
    assert start is not None, title
    j = start + 3
    while j < len(src) - 2 and not (src[j].startswith("// ═") and src[j + 2].startswith("// ═") and not src[j + 1].startswith("// ═")):
        j += 1
    return src[start:j]


def main():
    src = IND.read_text(encoding="utf-8").split("\n")
    inputs = [l for l in section(src, "INPUTS") if not l.startswith(DROP_INPUTS)]
    inputs = [l.replace('"Close tracked position on opposite signal"', '"Close position on opposite signal"')
               .replace('"Close tracked position on EXIT warning"', '"Close position on EXIT warning (CHoCH against / HTF flip)"')
               .replace('"Funding estimate % per 8h (PnL display only)"', '"Funding estimate % per 8h (stats table only)"')
              for l in inputs]
    helpers, skip = [], False
    for l in section(src, "TYPES & HELPERS"):
        if l.startswith("type Trade"):
            skip = True
            continue
        if skip:
            if l.strip() == "":
                skip = False
            continue
        helpers.append(l)
    # drop indicator-only helpers (multi-line definitions)
    out_h, i = [], 0
    while i < len(helpers):
        l = helpers[i]
        if l.startswith("f_compact(") or l.startswith("f_bucket("):
            i += 1
            while i < len(helpers) and helpers[i].startswith("    "):
                i += 1
            continue
        out_h.append(l)
        i += 1
    core = section(src, "CORE SERIES")
    mtf = [l for l in section(src, "MULTI-TIMEFRAME") if not l.startswith("float sD")]
    struct = section(src, "STRUCTURE & LIQUIDITY ENGINE")
    setup = section(src, "SETUP + SCORE ENGINE")
    head = (PARTS / "head.pine").read_text(encoding="utf-8")
    exe = (PARTS / "exec.pine").read_text(encoding="utf-8")
    OUT.write_text(head + "\n".join(inputs + out_h + core + mtf + struct + setup) + exe, encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
