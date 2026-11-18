"""
Scope-aware static checker for the CFE Pine Script v6 files (complements tools/check_pine.py).

It is NOT the TradingView compiler (no type inference), but it catches the error classes that most often
break a first compile:
  * undefined identifiers and use-before-declaration (Pine requires declaration before use; globals used
    inside a function must be declared before the function)
  * re-declaration of a name in the same scope
  * unknown fields of user-defined types (UDT.new(...) arguments and obj.field accesses)
  * wrong named / too many positional arguments for user-defined functions
  * built-in namespace members that are not on the Pine v6 whitelist below
  * v6 breaking changes: `transp=` / `when=` arguments, history reference on literals, duplicate named
    arguments, linewidth < 1

    python tools/lint_pine.py pine/*.pine          (exit code 1 on errors)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pynescript.ast as A
from pynescript.ast import parse

# ---------------------------------------------------------------- Pine v6 built-ins used by CFE (whitelist)
BUILTIN_VARS = {"open", "high", "low", "close", "volume", "time", "time_close", "bar_index", "na", "hl2", "hlc3",
                "ohlc4", "last_bar_index", "timenow", "true", "false"}
BUILTIN_FUNCS = {"indicator", "strategy", "library", "plot", "plotshape", "plotchar", "plotarrow", "plotcandle", "hline",
                 "fill", "bgcolor", "barcolor", "alert", "alertcondition", "nz", "na", "fixnan", "hour", "minute",
                 "dayofmonth", "dayofweek", "month", "year", "timestamp", "bool", "int", "float", "string", "max_bars_back"}
TYPES = {"int", "float", "bool", "string", "color", "line", "label", "box", "table", "array", "map", "matrix",
         "linefill", "polyline", "footprint", "volume_row"}
NS = {
    "ta": {"ema", "sma", "rma", "wma", "atr", "rsi", "macd", "highest", "lowest", "percentrank", "stdev", "median",
           "pivothigh", "pivotlow", "crossover", "crossunder", "change", "tr", "cum", "valuewhen", "barssince"},
    "math": {"max", "min", "abs", "sign", "round", "sum", "log", "sqrt", "floor", "ceil", "pow", "avg"},
    "request": {"security", "security_lower_tf", "currency_rate", "footprint"},
    "syminfo": {"tickerid", "ticker", "prefix", "currency", "volumetype", "mintick", "basecurrency", "type", "mincontract"},
    "timeframe": {"period", "in_seconds", "change", "isintraday", "multiplier"},
    "barstate": {"isconfirmed", "islast", "isfirst", "isrealtime", "islastconfirmedhistory", "ishistory", "isnew"},
    "strategy": {"entry", "exit", "close", "close_all", "cancel", "cancel_all", "long", "short", "equity", "opentrades",
                 "closedtrades", "netprofit", "grossprofit", "grossloss", "max_drawdown", "max_drawdown_percent",
                 "account_currency", "position_size", "commission", "fixed", "cash", "percent_of_equity", "initial_capital"},
    "strategy.commission": {"percent", "cash_per_contract", "cash_per_order"},
    "strategy.opentrades": {"entry_id", "entry_price", "entry_bar_index", "entry_time", "size", "profit"},
    "strategy.closedtrades": {"entry_id", "entry_price", "entry_bar_index", "entry_time", "exit_price", "exit_time",
                              "exit_bar_index", "size", "profit", "first_index", "commission"},
    "array": {"new", "from", "size", "get", "set", "push", "pop", "shift", "unshift", "clear", "remove", "insert", "copy"},
    "map": {"new", "put", "get", "contains", "keys", "values", "size", "remove", "clear"},
    "str": {"tostring", "format", "length", "contains", "replace_all", "upper", "lower", "split", "trim"},
    "color": {"new", "rgb", "gray", "white", "black", "red", "green", "blue", "teal", "orange", "yellow", "purple",
              "aqua", "lime", "silver", "maroon", "navy", "olive", "fuchsia"},
    "line": {"new", "delete", "set_x1", "set_x2", "set_y1", "set_y2", "set_xy1", "set_xy2", "set_color", "set_style",
             "set_width", "set_extend", "get_price", "style_dashed", "style_solid", "style_dotted", "style_arrow_right"},
    "label": {"new", "delete", "set_text", "set_xy", "set_x", "set_y", "set_color", "set_textcolor", "set_tooltip",
              "style_label_up", "style_label_down", "style_label_left", "style_label_right", "style_none",
              "style_label_center"},
    "box": {"new", "delete", "set_right", "set_top", "set_bottom", "set_bgcolor"},
    "table": {"new", "cell", "merge_cells", "cell_set_tooltip", "cell_set_text", "clear", "delete"},
    "input": {"string", "float", "int", "bool", "timeframe", "time", "color", "source", "symbol", "session", "price"},
    "plot": {"style_linebr", "style_columns", "style_line", "style_histogram", "style_circles", "style_stepline"},
    "shape": {"diamond", "triangleup", "triangledown", "circle", "cross", "xcross", "labelup", "labeldown", "square"},
    "location": {"belowbar", "abovebar", "top", "bottom", "absolute"},
    "size": {"tiny", "small", "normal", "large", "huge", "auto"},
    "position": {"top_right", "top_left", "bottom_right", "bottom_left", "top_center", "bottom_center", "middle_right",
                 "middle_left", "middle_center"},
    "text": {"align_left", "align_right", "align_center"},
    "display": {"data_window", "none", "all", "pane", "status_line", "price_scale"},
    "format": {"mintick", "volume", "percent", "price", "inherit"},
    "alert": {"freq_once_per_bar_close", "freq_once_per_bar", "freq_all"},
    "barmerge": {"lookahead_on", "lookahead_off", "gaps_on", "gaps_off"},
    "currency": {"USD", "EUR", "USDT"},
    "extend": {"right", "left", "both", "none"},
    "xloc": {"bar_index", "bar_time"},
    "footprint": {"buy_volume", "sell_volume", "delta", "poc", "vah", "val", "rows", "get_row_by_price"},
}
ROOT_NS = {k.split(".")[0] for k in NS}


class Lint:
    def __init__(self, path):
        self.path = path
        self.errors, self.warnings = [], []
        self.udts = {}          # name -> set(fields)
        self.funcs = {}         # name -> (params, required)

    # ------------------------------------------------------------------ helpers
    def err(self, node, msg):
        self.errors.append(f"{self.path}:{getattr(node, 'lineno', '?')}: {msg}")

    def warn(self, node, msg):
        self.warnings.append(f"{self.path}:{getattr(node, 'lineno', '?')}: {msg}")

    @staticmethod
    def dotted(node):
        parts = []
        while isinstance(node, A.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, A.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    def lookup(self, scopes, name):
        for sc in reversed(scopes):
            if name in sc:
                return sc[name]
        return None

    def type_of_annotation(self, t):
        """Return 'UDT' name, ('array', 'UDT') or None."""
        if t is None:
            return None
        if isinstance(t, A.Name):
            return t.id if t.id in self.udts else None
        if isinstance(t, A.Specialize):
            base = getattr(t, "value", None)
            arg = getattr(t, "args", None)
            if isinstance(arg, (list, tuple)):
                arg = arg[0] if arg else None
            if isinstance(base, A.Name) and base.id == "array" and isinstance(arg, A.Name) and arg.id in self.udts:
                return ("array", arg.id)
        return None

    # ------------------------------------------------------------------ expressions
    def expr(self, n, scopes):
        if n is None:
            return
        if isinstance(n, A.Name):
            if n.id in BUILTIN_VARS or n.id in BUILTIN_FUNCS or n.id in TYPES or n.id in ROOT_NS or n.id in self.udts:
                return
            if self.lookup(scopes, n.id) is None and n.id not in self.funcs:
                self.err(n, f"undefined identifier '{n.id}' (or used before its declaration)")
            return
        if isinstance(n, A.Attribute):
            d = self.dotted(n)
            if d is not None:
                root = d.split(".")[0]
                if root in ROOT_NS and self.lookup(scopes, root) is None:
                    ns, member = d.rsplit(".", 1)
                    if ns in NS:
                        if member not in NS[ns]:
                            self.err(n, f"unknown built-in '{d}' (not on the Pine v6 whitelist)")
                    elif d not in NS:
                        self.err(n, f"unknown built-in namespace '{ns}'")
                    return
                if root in self.udts:
                    if d != root + ".new":
                        self.err(n, f"unknown member '{d}'")
                    return
            # object field access
            self.expr(n.value, scopes)
            if isinstance(n.value, A.Name):
                t = self.lookup(scopes, n.value.id)
                if isinstance(t, str) and t in self.udts and n.attr not in self.udts[t]:
                    self.err(n, f"'{n.value.id}' is a {t}, which has no field '{n.attr}'")
            return
        if isinstance(n, A.Call):
            self.call(n, scopes)
            return
        if isinstance(n, A.Specialize):          # array.new<float>(...) – type arguments are not expressions
            self.expr(n.value, scopes)
            return
        if isinstance(n, A.Subscript):
            if isinstance(n.value, A.Constant):
                self.err(n, "history reference on a literal is not allowed in v6")
            self.expr(n.value, scopes)
            self.expr(getattr(n, "slice", None), scopes)
            return
        for field in ("left", "right", "operand", "test", "body", "orelse", "value"):
            v = getattr(n, field, None)
            if isinstance(v, A.AST):
                self.expr(v, scopes)
        for field in ("values", "comparators", "elts"):
            for v in getattr(n, field, None) or []:
                self.expr(v, scopes)

    def call(self, n, scopes):
        f = n.func
        names = [a.name for a in n.args if getattr(a, "name", None)]
        dup = {x for x in names if names.count(x) > 1}
        if dup:
            self.err(n, f"duplicate named argument(s) {sorted(dup)} (error in v6)")
        for a in n.args:
            if getattr(a, "name", None) in ("transp", "when"):
                self.err(n, f"argument '{a.name}' was removed in Pine v6")
            if getattr(a, "name", None) == "linewidth" and isinstance(a.value, A.Constant) and isinstance(a.value.value, (int, float)) and a.value.value < 1:
                self.err(n, "linewidth must be >= 1 in v6")
        if isinstance(f, A.Specialize):
            f = f.value
        d = self.dotted(f) if isinstance(f, (A.Attribute, A.Name)) else None
        if isinstance(f, A.Name) and f.id in self.funcs:
            params, required = self.funcs[f.id]
            pos = [a for a in n.args if not getattr(a, "name", None)]
            if len(pos) > len(params):
                self.err(n, f"{f.id}() takes {len(params)} arguments, got {len(pos)} positional")
            for nm in names:
                if nm not in params:
                    self.err(n, f"{f.id}() has no parameter '{nm}'")
            given = set(params[:len(pos)]) | set(names)
            missing = [p for p in required if p not in given]
            if missing:
                self.err(n, f"{f.id}() missing argument(s) {missing}")
        elif d and d.endswith(".new") and d[:-4] in self.udts:
            fields = self.udts[d[:-4]]
            for nm in names:
                if nm not in fields:
                    self.err(n, f"{d}() has no field '{nm}'")
            pos = [a for a in n.args if not getattr(a, "name", None)]
            if len(pos) > len(fields):
                self.err(n, f"{d}() got {len(pos)} positional arguments for {len(fields)} fields")
        else:
            self.expr(f, scopes)
        for a in n.args:
            self.expr(a.value, scopes)

    # ------------------------------------------------------------------ statements
    def declare(self, node, scopes, name, typ=True):
        if name in scopes[-1] and name != "_":
            self.err(node, f"'{name}' is already declared in this scope")
        elif self.lookup(scopes[:-1], name) is not None:
            self.warn(node, f"'{name}' shadows a variable of an outer scope")
        scopes[-1][name] = typ

    def stmts(self, body, scopes):
        for s in body:
            self.stmt(s, scopes)

    def block(self, body, scopes, extra=None):
        sc = dict(extra or {})
        self.stmts(body, scopes + [sc])

    def stmt(self, s, scopes):
        if isinstance(s, A.TypeDef):
            fields = set()
            for f in s.body:
                if isinstance(f, A.Assign) and isinstance(f.target, A.Name):
                    fields.add(f.target.id)
            self.udts[s.name] = fields
            return
        if isinstance(s, A.FunctionDef):
            params = [p.name for p in s.args]
            required = [p.name for p in s.args if getattr(p, "default", None) is None]
            self.funcs[s.name] = (params, required)
            fscope = {}
            for p in s.args:
                fscope[p.name] = self.type_of_annotation(getattr(p, "type", None)) or True
            self.block(s.body, scopes, fscope)
            return
        if isinstance(s, A.Assign):
            self.expr(s.value, scopes)
            t = self.type_of_annotation(getattr(s, "type", None))
            if t is None and isinstance(s.value, A.Call):
                dd = self.dotted(s.value.func) if isinstance(s.value.func, A.Attribute) else None
                if dd and dd.endswith(".new") and dd[:-4] in self.udts:
                    t = dd[:-4]
            if isinstance(s.target, A.Tuple):
                for e in s.target.elts:
                    self.declare(s, scopes, e.id)
            else:
                self.declare(s, scopes, s.target.id, t or True)
            return
        if isinstance(s, (A.ReAssign, A.AugAssign)):
            self.expr(s.value, scopes)
            tg = s.target
            if isinstance(tg, A.Name):
                if self.lookup(scopes, tg.id) is None:
                    self.err(s, f"assignment to undeclared variable '{tg.id}'")
            else:
                self.expr(tg, scopes)
            return
        if isinstance(s, A.Expr):
            v = s.value
            if isinstance(v, A.If):
                self.if_(v, scopes)
            elif isinstance(v, A.ForTo):
                self.expr(v.start, scopes); self.expr(v.end, scopes); self.expr(getattr(v, "step", None), scopes)
                self.block(v.body, scopes, {v.target.id: True})
            elif isinstance(v, A.ForIn):
                self.expr(v.iter, scopes)
                ext = {}
                it_t = None
                if isinstance(v.iter, A.Name):
                    it_t = self.lookup(scopes, v.iter.id)
                tgt = v.target
                if isinstance(tgt, A.Tuple):
                    for e in tgt.elts:
                        ext[e.id] = True
                else:
                    ext[tgt.id] = it_t[1] if isinstance(it_t, tuple) else True
                self.block(v.body, scopes, ext)
            elif isinstance(v, A.While):
                self.expr(v.test, scopes)
                self.block(v.body, scopes)
            elif isinstance(v, A.Switch):
                self.expr(getattr(v, "subject", None), scopes)
                for c in v.cases:
                    self.expr(getattr(c, "pattern", None), scopes)
                    self.block(c.body, scopes)
            else:
                self.expr(v, scopes)
            return
        if isinstance(s, (A.Break, A.Continue)):
            return

    def if_(self, v, scopes):
        self.expr(v.test, scopes)
        self.block(v.body, scopes)
        orelse = v.orelse or []
        if len(orelse) == 1 and isinstance(orelse[0], A.Expr) and isinstance(orelse[0].value, A.If):
            self.if_(orelse[0].value, scopes)
        else:
            self.block(orelse, scopes)

    def run(self):
        src = Path(self.path).read_text(encoding="utf-8")
        tree = parse(src)
        if not any("//@version=6" in a for a in tree.annotations):
            self.err(tree, "missing //@version=6")
        self.stmts(tree.body, [{}])
        return self


def main(paths):
    bad = 0
    for p in paths:
        L = Lint(p).run()
        print(f"{p}: {len(L.errors)} error(s), {len(L.warnings)} warning(s)")
        for e in L.errors:
            print("  ERROR", e)
        for w in L.warnings[:20]:
            print("  warn ", w)
        bad += len(L.errors)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or [str(p) for p in sorted((Path(__file__).resolve().parents[1] / "pine").glob("*.pine"))]))
