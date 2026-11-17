"""Syntax check of the Pine files with an independent parser (pynescript) + negative control.
This does NOT replace compiling in TradingView (no type checking), but catches syntax/indentation errors."""
from pathlib import Path

from pynescript.ast import parse

ROOT = Path(__file__).resolve().parents[1]
ok = True
for f in sorted((ROOT / "pine").glob("*.pine")):
    src = f.read_text(encoding="utf-8")
    try:
        parse(src)
        print(f"OK     {f.name}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"ERROR  {f.name}: {str(e)[:300]}")
# negative control: a broken copy must fail
try:
    parse("//@version=6\nindicator('x')\nif close > open (\n    x = 1\n")
    print("negative control FAILED (parser accepted broken code)")
    ok = False
except Exception:
    print("negative control OK (broken code rejected)")
raise SystemExit(0 if ok else 1)
