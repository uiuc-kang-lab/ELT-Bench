"""Stage-1 content check against stored reference values (no reference DB).

Two steps:

  build     Compute reference values once from a database that passed stage 1
            (e.g. ELT_STAGE1_REF) and store them in
            stage1_reference/<warehouse>.json.
  evaluate  Check a run's database against that file only.

Rules (same as eva_stage1_content.py, made reproducible across sessions):
  * Ignored columns: _AIRBYTE_*, _AB_* (CDC, source-file metadata) and
    MongoDB's _ID — they differ per sync/upload/setup and no task schema
    lists them.
  * Canonical column order: reference column names, sorted.
  * Fixed value -> string rules per reference type (see `canon`); timestamps
    are converted to UTC with an explicit format, so session settings do not
    matter. FLOAT keeps 15 significant digits (DBL_DIG): every value written
    with <= 15 significant digits renders the same even if a load path moved
    it by an ULP or two, while real changes down to ~1e-15 relative show up.
  * A run column whose type differs from the reference is converted to the
    reference type first (numbers directly, everything else via text).
  * Lenient JSON mode: reference columns missing from a run table that has a
    JSON `DATA` column (MongoDB source with schema_enforced = false) are
    extracted from it by key (case-insensitive) and converted to the
    reference type (JSON numbers directly, so no digits are lost).
  * Per table one query computes the row count, an order-independent
    HASH_AGG over all canonical columns, and one HASH_AGG per column.
  * Per column the reference also stores summary statistics (non-null and
    distinct counts, min/max, numeric sum, text length, ...). They do not
    decide pass/fail; for columns whose hash differs they say how the run
    differs (e.g. "93 values became NULL").
  * Probe: a fixed set of literal rows is rendered and hashed with the same
    rules; `evaluate` refuses to run if the probe hash changed (e.g. a
    warehouse release changed hashing or formatting).

Scores per run: tasks passed (every table identical), tasks whose row counts
all match (what the old stage 1 checked), tables present / with matching row
counts / identical, and column fidelity = identical columns / reference
columns (a missing table counts all its columns as wrong).

Reference values are per warehouse; only Snowflake is implemented.

Usage:
    python eva_stage1_stored.py build --reference-db elt_stage1_ref
    python eva_stage1_stored.py evaluate --database codex_gpt6astra --folder codex-cli-gpt-6-astra
"""

from __future__ import annotations

import argparse
import collections
import datetime
import decimal
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import snowflake.connector

# 2: FLOAT via 'TM9' (16 significant digits) instead of to_varchar's ~9 decimals.
# 3: FLOAT with 15 significant digits; JSON numbers and number->number type
#    differences converted without going through text; per-column statistics.
RULES_VERSION = 3
EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVALUATION_DIR.parent
REFERENCE_DIR = EVALUATION_DIR / "stage1_reference"
SESSION_PARAMETERS = {
    "TIMEZONE": "UTC",
    "TIMESTAMP_OUTPUT_FORMAT": "YYYY-MM-DD HH24:MI:SS.FF9 TZHTZM",
    "TIMESTAMP_NTZ_OUTPUT_FORMAT": "YYYY-MM-DD HH24:MI:SS.FF9",
    "DATE_OUTPUT_FORMAT": "YYYY-MM-DD",
    "BINARY_OUTPUT_FORMAT": "HEX",
    # Always recompute: identical query text would otherwise be answered from
    # Snowflake's 24 h result cache, making the reported timing meaningless.
    "USE_CACHED_RESULT": False,
}
TEXT_TYPES = ("TEXT", "VARCHAR", "STRING")
JSON_TYPES = ("VARIANT", "OBJECT", "ARRAY")
SUM_RTOL = 1e-9  # only for reporting sums in diagnoses (float sums depend on summation order)
_local = threading.local()


# ---------- rules ----------

def is_meta(column: str) -> bool:
    c = column.upper()
    return c.startswith("_AIRBYTE") or c.startswith("_AB_") or c == "_ID"


def q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def is_numeric(sql_type: str) -> bool:
    t = sql_type.upper()
    return t.startswith("NUMBER") or t == "FLOAT"


def canon(expr: str, sql_type: str) -> str:
    """SQL rendering `expr` (of type `sql_type`) as a fixed canonical string."""
    t = sql_type.upper()
    if t in TEXT_TYPES:
        return f"({expr})::varchar"
    if t.startswith("NUMBER"):
        return f"to_varchar({expr})"
    if t == "FLOAT":
        # 15 significant digits in scientific notation ('-1.4844252E2'); the
        # format pads with spaces and cannot render 0 (-0.0 would give
        # '-0.E0'), NaN, +-inf or subnormals, so those use fixed spellings.
        return (f"case when {expr} = 0 then '0' "
                f"when not (abs({expr}) between 2.2250738585072014e-308 and 1.7976931348623157e308) "
                f"then to_varchar({expr}) "
                f"else replace(to_varchar({expr}, '9.99999999999999EE'), ' ', '') end")
    if t == "BOOLEAN":
        return f"case when ({expr}) is null then null when ({expr}) then 'true' else 'false' end"
    if t == "DATE":
        return f"to_varchar({expr}, 'YYYY-MM-DD')"
    if t == "TIME":
        return f"to_varchar({expr}, 'HH24:MI:SS.FF9')"
    if t == "TIMESTAMP_NTZ":
        return f"to_varchar({expr}, 'YYYY-MM-DD HH24:MI:SS.FF9')"
    if t in ("TIMESTAMP_TZ", "TIMESTAMP_LTZ"):
        return f"to_varchar(convert_timezone('UTC', {expr})::timestamp_ntz, 'YYYY-MM-DD HH24:MI:SS.FF9')"
    if t in JSON_TYPES:
        return f"to_json({expr})"
    if t == "BINARY":
        return f"hex_encode({expr})"
    return f"to_varchar({expr})"


def from_variant(v: str, t: str) -> str:
    """Value of VARIANT expression `v` as reference type `t`."""
    if t in JSON_TYPES:
        return v
    if t in TEXT_TYPES:
        return f"to_varchar({v})"
    if is_numeric(t):
        # JSON numbers convert directly: to_varchar of a DOUBLE inside a
        # VARIANT keeps only ~10 digits (3.141592653589793 -> '3.141592654').
        return f"iff(is_integer({v}) or is_decimal({v}) or is_double({v}), {v}::{t}, try_cast(to_varchar({v}) as {t}))"
    if t == "BOOLEAN":
        return f"iff(is_boolean({v}), {v}::boolean, try_cast(to_varchar({v}) as boolean))"
    return f"try_cast(to_varchar({v}) as {t})"


def typed_run_expr(ref_type: str, column: str | None = None, run_type: str | None = None,
                   json_column: str | None = None, json_key: str | None = None) -> str:
    """Expression of the reference column's type, read from a run table."""
    t = ref_type.upper()
    if json_column is not None:  # lenient JSON mode
        return from_variant(f"strip_null_value({q(json_column)}:{q(json_key)})", t)
    u = run_type.upper()
    if u == t:
        return q(column)
    if u in JSON_TYPES:
        return from_variant(q(column), t)
    if is_numeric(u) and is_numeric(t):
        return f"{q(column)}::{t}"
    if t in TEXT_TYPES:
        return f"to_varchar({q(column)})"
    if t in JSON_TYPES:
        return f"try_parse_json(to_varchar({q(column)}))"
    return f"try_cast(to_varchar({q(column)}) as {t})"


def stat_exprs(x: str, sql_type: str) -> list[tuple[str, str]]:
    """(name, SQL aggregate) summary statistics of typed expression `x`."""
    t = sql_type.upper()
    out = [("non_null", f"count({x})"), ("distinct", f"count(distinct {canon(x, t)})")]
    if is_numeric(t):
        out += [("min", canon(f"min({x})", t)), ("max", canon(f"max({x})", t)), ("sum", f"sum(({x})::double)")]
    elif t in TEXT_TYPES:
        out += [("min", f"left(min({x}), 100)"), ("max", f"left(max({x}), 100)"),
                ("total_length", f"sum(length({x}))")]
    elif t == "BOOLEAN":
        out += [("true", f"count_if({x})")]
    elif t in JSON_TYPES:
        out += [("total_length", f"sum(length(to_json({x})))")]
    else:  # dates, times, timestamps, binary
        out += [("min", canon(f"min({x})", t)), ("max", canon(f"max({x})", t))]
    return out


def stat_differs(name: str, ref, run) -> bool:
    if name == "sum" and ref is not None and run is not None:
        return abs(ref - run) > SUM_RTOL * max(abs(ref), abs(run)) + 1e-12
    return ref != run


def plain(v):
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


PROBE_ROWS = [
    "('Abc é', 123, 0.1, 1e20, 123456789.123456789, true, '2024-01-02', "
    "'2024-01-02 03:04:05.123456789', '2024-01-02 03:04:05.5 +02:00', '{\"b\":1,\"a\":[1,2.5,null]}')",
    "('', -7, -0.0000123, 3, 0.30000000000000004, false, '1970-01-01', "
    "'1970-01-01 00:00:00', '1999-12-31 23:59:59 -05:00', '[\"x\",{\"k\":\"v\"}]')",
    "('f', 0, 0.12345678901234567, -0.0, 1.0000000000000002, null, null, null, null, null)",
    "(null, null, null, null, null, null, null, null, null, null)",
]
PROBE_COLUMNS = [  # (name, type, cast from the VALUES literal)
    ("T", "TEXT", "column1::varchar"), ("N", "NUMBER(38,0)", "column2::number(38,0)"),
    ("F1", "FLOAT", "column3::float"), ("F2", "FLOAT", "column4::float"),
    ("F3", "FLOAT", "column5::float"), ("B", "BOOLEAN", "column6::boolean"),
    ("D", "DATE", "column7::date"), ("TS", "TIMESTAMP_NTZ", "column8::timestamp_ntz"),
    ("TZ", "TIMESTAMP_TZ", "column9::timestamp_tz"), ("V", "VARIANT", "parse_json(column10)"),
]


def probe(cur) -> dict:
    typed = ", ".join(f"{cast} as {q(name)}" for name, _, cast in PROBE_COLUMNS)
    exprs = [canon(q(name), ty) for name, ty, _ in PROBE_COLUMNS]
    src = f"(select {typed} from values {', '.join(PROBE_ROWS)})"
    cur.execute(f"select {', '.join(exprs)} from {src} order by 1 nulls last")
    rendered = [list(r) for r in cur.fetchall()]
    cur.execute(f"select hash_agg({', '.join(exprs)}) from {src}")
    return {"hash": str(cur.fetchone()[0]), "rendered": rendered}


# ---------- connection / metadata ----------

def credentials(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return {k: raw[k] for k in ("account", "user", "password", "role", "warehouse") if raw.get(k)}


def cursor(creds: dict):
    if not hasattr(_local, "cur"):
        _local.conn = snowflake.connector.connect(login_timeout=60, session_parameters=SESSION_PARAMETERS, **creds)
        _local.cur = _local.conn.cursor()
    return _local.cur


def columns_by_table(cur, database: str) -> dict:
    """{(SCHEMA, table_lower): (TableName, [(column, sql_type), ...])}."""
    cur.execute(
        "select table_schema, table_name, column_name, data_type, numeric_precision, numeric_scale "
        f"from {q(database.upper())}.information_schema.columns where table_schema <> 'INFORMATION_SCHEMA' "
        "order by table_schema, table_name, ordinal_position")
    out: dict = {}
    for s, t, c, ty, prec, scale in cur.fetchall():
        sql_type = f"NUMBER({prec},{scale})" if ty == "NUMBER" and prec is not None else ty
        out.setdefault((s, t.lower()), (t, []))[1].append((c, sql_type))
    return out


class Timer:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.by_kind: dict = collections.defaultdict(list)

    def run(self, cur, kind: str, sql: str):
        t = time.perf_counter()
        cur.execute(sql)
        rows = cur.fetchall()
        with self.lock:
            self.by_kind[kind].append(time.perf_counter() - t)
        return rows

    def summary(self) -> dict:
        return {k: {"queries": len(v), "total_s": round(sum(v), 1), "mean_s": round(statistics.mean(v), 3),
                    "max_s": round(max(v), 2)} for k, v in self.by_kind.items()}


def table_stats_sql(fqn: str, exprs: list[str], extra: list[str] = ()) -> str:
    return (f"select count(*), hash_agg({', '.join(exprs)}), "
            + ", ".join([f"hash_agg({e})" for e in exprs] + list(extra)) + f" from {fqn}")


# ---------- build ----------

def build(args) -> None:
    creds = credentials(args.credential)
    table_list = json.loads(args.table_json.read_text())
    t0 = time.perf_counter()
    cur = cursor(creds)
    cur.execute("select current_version()")
    version = cur.fetchone()[0]
    probe_value = probe(cur)
    meta = columns_by_table(cur, args.reference_db)
    timer = Timer()
    db = q(args.reference_db.upper())

    def one(schema: str, table: str):
        name, cols = meta[(schema.upper(), table.lower())]
        data = sorted(((c, ty) for c, ty in cols if not is_meta(c)), key=lambda x: x[0].upper())
        exprs = [canon(q(c), ty) for c, ty in data]
        stats = [(c.upper(), k, sql) for c, ty in data for k, sql in stat_exprs(q(c), ty)]
        row = timer.run(cursor(creds), "table stats",
                        table_stats_sql(f"{db}.{q(schema.upper())}.{q(name)}", exprs, [s for _, _, s in stats]))[0]
        n = len(data)
        column_stats: dict = collections.defaultdict(dict)
        for (c, k, _), v in zip(stats, row[2 + n:]):
            column_stats[c][k] = plain(v)
        return {"rows": row[0], "columns": [[c.upper(), ty] for c, ty in data], "hash": str(row[1]),
                "column_hashes": {c.upper(): str(h) for (c, _), h in zip(data, row[2:2 + n])},
                "column_stats": column_stats}

    jobs = [(s, t) for s in sorted(table_list) for t in table_list[s]]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {job: pool.submit(one, *job) for job in jobs}
    tables: dict = collections.defaultdict(dict)
    for (s, t), f in futures.items():
        tables[s][t] = f.result()
    elapsed = time.perf_counter() - t0
    out = {
        "warehouse": "snowflake", "rules_version": RULES_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source_database": args.reference_db.upper(), "snowflake_version": version,
        "notes": args.notes, "probe": probe_value, "tables": tables,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1))
    print(f"built {args.out} from {args.reference_db}: {len(jobs)} tables in {len(tables)} tasks, "
          f"{elapsed:.1f}s ({args.workers} workers); probe hash {probe_value['hash']}; snowflake {version}")


# ---------- evaluate ----------

def evaluate(args) -> None:
    ref = json.loads(args.reference.read_text())
    if ref.get("rules_version") != RULES_VERSION:
        raise SystemExit(f"reference rules_version {ref.get('rules_version')} != {RULES_VERSION}; rebuild it")
    creds = credentials(args.credential)
    timer = Timer()
    T0 = time.perf_counter()
    t = time.perf_counter()
    cur = cursor(creds)
    t_connect = time.perf_counter() - t
    t = time.perf_counter()
    now_probe = probe(cur)
    t_probe = time.perf_counter() - t
    if now_probe["hash"] != ref["probe"]["hash"]:
        changed = [(a, b) for a, b in zip(ref["probe"]["rendered"], now_probe["rendered"]) if a != b]
        raise SystemExit("probe hash changed: hashing or formatting differs from when the reference was built "
                         f"(rendering differences: {changed or 'none, hash function changed'}). Rebuild the reference.")
    t = time.perf_counter()
    run_meta = columns_by_table(cur, args.database)
    t_meta = time.perf_counter() - t
    db = q(args.database.upper())
    schemas = sorted(ref["tables"])
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        schemas = [s for s in schemas if s in wanted]

    def one(schema: str, table: str) -> dict:
        r = ref["tables"][schema][table]
        names = [c for c, _ in r["columns"]]
        found = run_meta.get((schema.upper(), table.lower()))
        if found is None:
            return {"status": "missing_in_run", "reference_rows": r["rows"],
                    "columns_total": len(names), "columns_matching": 0}
        name, cols = found
        fqn = f"{db}.{q(schema.upper())}.{q(name)}"
        run_cols = {c.upper(): (c, ty) for c, ty in cols if not is_meta(c)}
        typed, missing, extracted = {}, [], []
        json_cols = [c for c, ty in run_cols.values() if ty in ("VARIANT", "OBJECT") and c.upper() == "DATA"]
        keys = None
        for col, ref_type in r["columns"]:
            if col in run_cols:
                c, ty = run_cols[col]
                typed[col] = typed_run_expr(ref_type, column=c, run_type=ty)
                continue
            if json_cols and keys is None:
                rows = timer.run(cursor(creds), "json keys",
                                 f"select distinct f.key from {fqn} r, lateral flatten(input => r.{q(json_cols[0])}) f")
                keys = {k.upper(): k for (k,) in rows}
            if keys and col in keys:
                typed[col] = typed_run_expr(ref_type, json_column=json_cols[0], json_key=keys[col])
                extracted.append(col)
            else:
                missing.append(col)
        exprs = [canon(typed[c], ty) if c in typed else "null" for c, ty in r["columns"]]
        row = timer.run(cursor(creds), "table stats", table_stats_sql(fqn, exprs))[0]
        matching = [c for c, h in zip(names, row[2:]) if c in typed and str(h) == r["column_hashes"][c]]
        differing = [c for c in names if c in typed and c not in matching]
        res = {"reference_rows": r["rows"], "run_rows": row[0],
               "columns_total": len(names), "columns_matching": len(matching)}
        if differing:
            res["differing_columns"] = differing
        if missing:
            res["missing_columns"] = missing
        if extracted:
            res["extracted_from_json"] = extracted
        extra = sorted(set(run_cols) - set(names))
        if extra:
            res["only_in_run"] = extra
        if str(row[1]) == r["hash"] and not missing:
            res["status"] = "identical_via_json" if extracted else "identical"
            return res
        res["status"] = "different"
        if not differing and not missing and row[0] == r["rows"]:
            # Every column matches as a whole, but values are paired with
            # different rows (e.g. two rows' values swapped).
            res["note"] = "rows misaligned: each column's values match, their combination per row does not"
        if differing:
            # Explain each differing column with the stored statistics.
            types = dict(r["columns"])
            stats = [(c, k, sql) for c in differing for k, sql in stat_exprs(typed[c], types[c])]
            got = timer.run(cursor(creds), "diagnosis", f"select {', '.join(s for _, _, s in stats)} from {fqn}")[0]
            diagnosis: dict = collections.defaultdict(dict)
            for (c, k, _), v in zip(stats, got):
                want = r["column_stats"][c][k]
                if stat_differs(k, want, plain(v)):
                    diagnosis[c][k] = [want, plain(v)]
            res["diagnosis"] = {c: diagnosis.get(c) or "values differ; counts, min/max and sums agree"
                                for c in differing}
        return res

    jobs = [(s, tb) for s in schemas for tb in ref["tables"][s]]
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {job: pool.submit(one, *job) for job in jobs}
    results: dict = collections.defaultdict(dict)
    for (s, tb), f in futures.items():
        try:
            results[s][tb] = f.result()
        except Exception as e:
            results[s][tb] = {"status": "error", "error": str(e)[:500],
                              "columns_total": len(ref["tables"][s][tb]["columns"]), "columns_matching": 0}
    t_tables = time.perf_counter() - t
    total = time.perf_counter() - T0

    passing = ("identical", "identical_via_json")
    rows_ok = lambda r: r.get("run_rows") is not None and r["run_rows"] == r.get("reference_rows")
    tasks = {}
    for s in schemas:
        v = results[s].values()
        tasks[s] = {"passed": all(r["status"] in passing for r in v), "row_counts_match": all(rows_ok(r) for r in v),
                    "columns_total": sum(r["columns_total"] for r in v),
                    "columns_matching": sum(r["columns_matching"] for r in v)}
    every = [r for v in results.values() for r in v.values()]
    col_total = sum(r["columns_total"] for r in every)
    col_ok = sum(r["columns_matching"] for r in every)
    summary = {
        "tasks": {"total": len(schemas), "passed": sum(x["passed"] for x in tasks.values()),
                  "row_counts_match": sum(x["row_counts_match"] for x in tasks.values())},
        "tables": {"total": len(every), "present": sum(r["status"] != "missing_in_run" for r in every),
                   "row_counts_match": sum(rows_ok(r) for r in every),
                   "identical": sum(r["status"] in passing for r in every)},
        "columns": {"total": col_total, "identical": col_ok,
                    "fidelity": round(col_ok / col_total, 4) if col_total else None},
    }
    timing = {"total_s": round(total, 1), "connect_s": round(t_connect, 1), "probe_s": round(t_probe, 1),
              "metadata_s": round(t_meta, 1), "tables_s": round(t_tables, 1), "workers": args.workers,
              "queries": timer.summary()}
    out_dir = EVALUATION_DIR / "agent_results" / args.folder
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage1_stored.json").write_text(json.dumps(
        {"database": args.database, "reference": str(args.reference), "rules_version": RULES_VERSION,
         "reference_generated_at": ref["generated_at"], "timing": timing, "summary": summary,
         "tasks_passed": summary["tasks"]["passed"], "tasks": tasks, "tables": results},
        indent=2, default=str))
    with open(out_dir / "stage1_stored.log", "w") as log:  # results.log-style lines
        for s in schemas:
            bad = {tb: r["status"] for tb, r in results[s].items() if r["status"] not in passing}
            log.write(f"Success: {s} content verified\n" if tasks[s]["passed"] else
                      f"Error: {s} {json.dumps(bad)} columns {tasks[s]['columns_matching']}/{tasks[s]['columns_total']}\n")

    statuses = collections.Counter(r["status"] for r in every)
    ts, tb, cs = summary["tasks"], summary["tables"], summary["columns"]
    print(f"{args.database}: tasks passed {ts['passed']}/{ts['total']} (row counts match: {ts['row_counts_match']}) | "
          f"tables identical {tb['identical']}/{tb['total']}, row counts {tb['row_counts_match']}, present {tb['present']} | "
          f"columns {cs['identical']}/{cs['total']} ({100 * (cs['fidelity'] or 0):.2f}%) | {dict(statuses)}")
    print(f"  time: total {total:.1f}s = connect {t_connect:.1f}s + probe {t_probe:.1f}s + metadata {t_meta:.1f}s "
          f"+ tables {t_tables:.1f}s ({args.workers} workers)")
    for k, v in timer.summary().items():
        print(f"    {k:12s} {v['queries']:4d} queries, {v['total_s']:6.1f}s summed, mean {v['mean_s']:.3f}s, max {v['max_s']:.2f}s")
    for s, v in sorted(results.items()):
        for tbl, r in sorted(v.items()):
            if r["status"] != "identical":
                detail = {k: r[k] for k in ("reference_rows", "run_rows", "columns_matching", "columns_total",
                                            "missing_columns", "extracted_from_json", "note", "diagnosis", "error")
                          if r.get(k) is not None and r.get(k) != []}
                print(f"  {s}.{tbl}: {r['status']} {json.dumps(detail, default=str)[:400]}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--credential", type=Path, default=PROJECT_DIR / "setup/destination/snowflake_credential.json")
    common.add_argument("--workers", type=int, default=8)
    b = sub.add_parser("build", parents=[common])
    b.add_argument("--reference-db", required=True)
    b.add_argument("--table-json", type=Path, default=EVALUATION_DIR / "table.json")
    b.add_argument("--out", type=Path, default=REFERENCE_DIR / "snowflake.json")
    b.add_argument("--notes", default="")
    e = sub.add_parser("evaluate", parents=[common])
    e.add_argument("--database", required=True)
    e.add_argument("--folder", required=True)
    e.add_argument("--reference", type=Path, default=REFERENCE_DIR / "snowflake.json")
    e.add_argument("--only", default="")
    args = p.parse_args()
    build(args) if args.cmd == "build" else evaluate(args)


if __name__ == "__main__":
    main()
