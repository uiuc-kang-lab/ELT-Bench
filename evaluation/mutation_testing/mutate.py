"""SQL mutation operators for testing the stage-2 verifier.

Each operator rewrites one site of a ground-truth query (a parsed sqlglot
tree, Snowflake dialect) and returns the mutated SQL. Operators model common
transformation mistakes, including ones seen in agent runs:

  drop_filter    remove one WHERE/HAVING conjunct (or the whole clause)
  join_type      INNER JOIN <-> LEFT JOIN
  join_key       replace a join-key column with another column of the same
                 table and type family
  aggregate      SUM <-> AVG, MIN <-> MAX, COUNT(x) <-> COUNT(DISTINCT x)
  boundary       > <-> >=, < <-> <=
  distinct       drop SELECT DISTINCT
  null_handling  COALESCE/IFNULL/NVL(a, b, ...) -> a
  tie_break      window ORDER BY: flip the first key, or drop the last key
  scale          x * 100 -> x (percentage as a fraction), ROUND(x, n) -> x
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterator

import sqlglot
from sqlglot import exp

DIALECT = "snowflake"
OPERATORS = ("drop_filter", "join_type", "join_key", "aggregate", "boundary",
             "distinct", "null_handling", "tie_break", "scale")

# column type families for join_key replacements
_NUMERIC = ("NUMBER", "DECIMAL", "INT", "FLOAT", "DOUBLE", "REAL")
_TEXT = ("TEXT", "VARCHAR", "CHAR", "STRING")
_TIME = ("DATE", "TIME", "TIMESTAMP")


def type_family(data_type: str) -> str:
    t = (data_type or "").upper()
    for name, prefixes in (("number", _NUMERIC), ("text", _TEXT), ("time", _TIME)):
        if t.startswith(prefixes):
            return name
    return t or "other"


def _conjuncts(cond: exp.Expression) -> list[exp.Expression]:
    if isinstance(cond, exp.Paren) and isinstance(cond.this, exp.And):
        cond = cond.this
    if isinstance(cond, exp.And):
        return _conjuncts(cond.left) + _conjuncts(cond.right)
    return [cond]


def _and(parts: list[exp.Expression]) -> exp.Expression:
    out = parts[0].copy()
    for p in parts[1:]:
        out = exp.and_(out, p.copy())
    return out


def _tables_in_scope(select: exp.Select) -> dict[str, exp.Table]:
    """alias (or name) -> physical table for the FROM/JOIN items of a SELECT."""
    out: dict[str, exp.Table] = {}
    sources = []
    if select.args.get("from"):
        sources.append(select.args["from"].this)
    for j in select.args.get("joins") or []:
        sources.append(j.this)
    for src in sources:
        if isinstance(src, exp.Table) and src.args.get("db"):
            out[(src.alias or src.name).lower()] = src
    return out


# ---------------------------------------------------------------------------
# Site enumeration: each site is (operator, description, edit) where `edit`
# mutates the node at the same walk position in a fresh copy of the tree.
# ---------------------------------------------------------------------------

Edit = Callable[[exp.Expression], None]


def _sites(tree: exp.Expression, columns: dict[str, list[tuple[str, str]]],
           rng: random.Random) -> Iterator[tuple[str, str, int, Edit]]:
    nodes = list(tree.walk())
    for idx, node in enumerate(nodes):
        # drop_filter
        if isinstance(node, (exp.Where, exp.Having)):
            kind = "WHERE" if isinstance(node, exp.Where) else "HAVING"
            parts = _conjuncts(node.this)
            if len(parts) > 1:
                for i, part in enumerate(parts):
                    rest = [p for j, p in enumerate(parts) if j != i]
                    yield ("drop_filter", f"drop {kind} conjunct: {part.sql(DIALECT)[:120]}", idx,
                           lambda n, rest=rest: n.set("this", _and(rest)))
            else:
                yield ("drop_filter", f"drop {kind}: {node.this.sql(DIALECT)[:120]}", idx,
                       lambda n: n.pop())

        if isinstance(node, exp.Join) and node.args.get("on") is not None:
            side = (node.args.get("side") or "").upper()
            kind = (node.args.get("kind") or "").upper()
            if side == "LEFT":
                yield ("join_type", f"LEFT JOIN -> INNER JOIN ({node.this.sql(DIALECT)[:60]})", idx,
                       lambda n: (n.set("side", None), n.set("kind", None)))
            elif not side and kind in ("", "INNER"):
                yield ("join_type", f"INNER JOIN -> LEFT JOIN ({node.this.sql(DIALECT)[:60]})", idx,
                       lambda n: (n.set("side", "LEFT"), n.set("kind", None)))

        # join_key: a column in an equality of a JOIN ... ON condition
        if isinstance(node, exp.Column) and columns:
            eq = node.parent
            on = eq.parent if eq is not None else None
            while on is not None and isinstance(on, (exp.And, exp.Paren)):
                on = on.parent
            if (isinstance(eq, exp.EQ) and isinstance(on, exp.Join)
                    and isinstance(eq.left, exp.Column) and isinstance(eq.right, exp.Column)):
                select = on.parent
                table = _tables_in_scope(select).get((node.table or "").lower()) \
                    if isinstance(select, exp.Select) else None
                if table is not None:
                    fqn = f"{table.catalog}.{table.db}.{table.name}".upper()
                    cols = columns.get(fqn, [])
                    own = {c: t for c, t in cols}.get(node.name.upper())
                    if own is not None:
                        # other business columns only: loader metadata
                        # (_AIRBYTE_*, _AB_*, _FIVETRAN_*) is not a plausible key
                        same = [c for c, t in cols
                                if c != node.name.upper() and not c.startswith("_")
                                and type_family(t) == type_family(own)]
                        for alt in rng.sample(same, min(2, len(same))):
                            yield ("join_key", f"join key {node.sql(DIALECT)} -> {node.table}.{alt.lower()}",
                                   idx, lambda n, alt=alt: n.set("this", exp.to_identifier(alt.lower())))

        if isinstance(node, exp.AggFunc):
            swap = {exp.Sum: exp.Avg, exp.Avg: exp.Sum, exp.Min: exp.Max, exp.Max: exp.Min}
            cls = swap.get(type(node))
            if cls is not None:
                yield ("aggregate", f"{type(node).__name__.upper()} -> {cls.__name__.upper()}: "
                                    f"{node.sql(DIALECT)[:80]}", idx,
                       lambda n, cls=cls: n.replace(cls(this=n.this.copy())))
            elif isinstance(node, exp.Count) and not isinstance(node.this, exp.Star) and node.this is not None:
                if isinstance(node.this, exp.Distinct):
                    yield ("aggregate", f"COUNT(DISTINCT x) -> COUNT(x): {node.sql(DIALECT)[:80]}", idx,
                           lambda n: n.set("this", n.this.expressions[0].copy()))
                else:
                    yield ("aggregate", f"COUNT(x) -> COUNT(DISTINCT x): {node.sql(DIALECT)[:80]}", idx,
                           lambda n: n.set("this", exp.Distinct(expressions=[n.this.copy()])))

        swap_cmp = {exp.GT: exp.GTE, exp.GTE: exp.GT, exp.LT: exp.LTE, exp.LTE: exp.LT}
        if type(node) in swap_cmp:
            cls = swap_cmp[type(node)]
            yield ("boundary", f"{node.sql(DIALECT)[:80]} -> {cls.__name__}", idx,
                   lambda n, cls=cls: n.replace(cls(this=n.this.copy(), expression=n.expression.copy())))

        if isinstance(node, exp.Select) and node.args.get("distinct") is not None:
            yield ("distinct", "drop SELECT DISTINCT", idx, lambda n: n.set("distinct", None))

        if isinstance(node, exp.Coalesce):
            yield ("null_handling", f"{node.sql(DIALECT)[:80]} -> first argument", idx,
                   lambda n: n.replace(n.this.copy()))

        if isinstance(node, exp.Window) and node.args.get("order") is not None:
            keys = node.args["order"].expressions
            if keys:
                yield ("tie_break", f"flip window ORDER BY {keys[0].sql(DIALECT)[:60]}", idx,
                       lambda n: n.args["order"].expressions[0].set(
                           "desc", not n.args["order"].expressions[0].args.get("desc")))
            if len(keys) > 1:
                yield ("tie_break", f"drop window tie-breaker {keys[-1].sql(DIALECT)[:60]}", idx,
                       lambda n: n.args["order"].expressions[-1].pop())

        if isinstance(node, exp.Mul):
            for side, other in (("this", "expression"), ("expression", "this")):
                lit = node.args.get(side)
                if isinstance(lit, exp.Literal) and lit.is_number and float(lit.this) == 100:
                    yield ("scale", f"drop * 100: {node.sql(DIALECT)[:80]}", idx,
                           lambda n, other=other: n.replace(n.args[other].copy()))
                    break
        if isinstance(node, exp.Round):
            yield ("scale", f"drop ROUND: {node.sql(DIALECT)[:80]}", idx,
                   lambda n: n.replace(n.this.copy()))


def mutants(sql: str, columns: dict[str, list[tuple[str, str]]] | None = None,
            per_operator: int = 3, seed: int = 0) -> list[dict[str, Any]]:
    """Up to `per_operator` distinct mutants per operator for one query."""
    rng = random.Random(seed)
    tree = sqlglot.parse_one(sql, read=DIALECT)
    base = tree.sql(DIALECT)
    by_op: dict[str, list[dict[str, Any]]] = {op: [] for op in OPERATORS}
    seen = {base}
    for op, desc, idx, edit in _sites(tree, columns or {}, rng):
        copy = tree.copy()
        node = list(copy.walk())[idx]
        try:
            edit(node)
            out = copy.sql(DIALECT)
        except Exception:  # an edit that does not apply to this shape
            continue
        if out in seen:
            continue
        seen.add(out)
        by_op[op].append({"operator": op, "description": desc, "sql": out})
    chosen = []
    for op in OPERATORS:
        cands = by_op[op]
        chosen.extend(rng.sample(cands, min(per_operator, len(cands))))
    return chosen


def referenced_tables(sql: str) -> list[str]:
    """Fully qualified physical tables (catalog.db.name, upper case) in a query."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    out = set()
    for t in tree.find_all(exp.Table):
        if t.args.get("catalog") and t.args.get("db"):
            out.add(f"{t.catalog}.{t.db}.{t.name}".upper())
    return sorted(out)
