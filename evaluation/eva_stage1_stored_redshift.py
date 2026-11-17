"""Stage-1 content check for Redshift against stored reference values.

Redshift counterpart of eva_stage1_stored.py (Snowflake). The hashes are
Redshift's own and are not comparable with the Snowflake reference.

Two steps:

  build     Compute reference values once from a database that passed stage 1
            (e.g. elt_stage1_ref, loaded by the ground-truth Airbyte pipelines)
            and store them in stage1_reference/redshift.json.
  evaluate  Check a run's database against that file only.

Rules:
  * Ignored columns: _airbyte_*, _ab_* (CDC, source-file metadata) and
    MongoDB's _id.
  * Canonical column order: reference column names, sorted.
  * Fixed value -> string rules per reference type (see `canon`): NUMERIC
    without trailing fractional zeros (so the scale does not matter), floats
    with Redshift's 15 significant digits and 0 for -0, booleans as
    true/false, dates/timestamps with explicit formats (TIMESTAMPTZ in UTC,
    microseconds), SUPER strings as their text, other SUPER values via
    json_serialize, SUPER NULL / JSON null as NULL.
  * A run column whose type differs from the reference is converted to the
    reference type first (numbers directly, everything else via text with
    TRY_CAST).
  * Lenient JSON mode: reference columns missing from a run table that has a
    SUPER `data` column (MongoDB source with schema_enforced = false) are read
    from it by key (case-insensitive match) and converted to the reference
    type.
  * Order-independent hashing (Redshift has no HASH_AGG): every value becomes
    md5(canonical string), or 'N' for NULL; a row hashes as md5 of its value
    hashes concatenated in canonical column order. A hex hash h counts as the
    integer strtol(left(h, 15), 16) (60 bits, NULL counts as 1), and a table
    hash / column hash is the exact NUMERIC sum of those over all rows, so it
    is independent of row order but sensitive to duplicates. One query per
    table returns the row count, the table hash and one hash per column.
  * Per column the reference also stores summary statistics (non-null and
    distinct counts, min/max, numeric sum, text length, ...). They do not
    decide pass/fail; for columns whose hash differs they say how the run
    differs (e.g. "93 values became NULL").
  * Probe: a fixed set of literal rows is rendered and hashed with the same
    rules; `evaluate` refuses to run if the probe hash changed (e.g. a
    Redshift release changed formatting).

Scores per run: tasks passed (every table identical), tasks whose row counts
all match, tables present / with matching row counts / identical, and column
fidelity = identical columns / reference columns (a missing table counts all
its columns as wrong).

Usage:
    python eva_stage1_stored_redshift.py build --reference-db elt_stage1_ref
    python eva_stage1_stored_redshift.py evaluate \
        --database claude_claude_opus_4_7_eltbench --folder claude-opus-4-7-redshift
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

import redshift_connector

# 2: SUPER renders strings as their text and NULL / JSON null as NULL (not
#    'null'); text -> SUPER via a string scalar; distinct counts on md5, so
#    values differing only in trailing blanks stay distinct.
RULES_VERSION = 2
EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVALUATION_DIR.parent
REFERENCE_DIR = EVALUATION_DIR / "stage1_reference"
SESSION_SETTINGS = [
    "SET timezone TO 'UTC'",
    "SET datestyle TO 'ISO, MDY'",
    # SUPER keys keep their case ("Name"); identifiers here are always quoted
    # with the catalog's spelling, so this changes nothing else.
    "SET enable_case_sensitive_identifier TO true",
    # Always recompute, so the reported timing is meaningful.
    "SET enable_result_cache_for_session TO off",
]
TEXT_TYPES = ("VARCHAR", "CHAR")
INT_TYPES = ("SMALLINT", "INTEGER", "BIGINT")
FLOAT_TYPES = ("DOUBLE PRECISION", "REAL")
TYPE_NAMES = {
    "character varying": "VARCHAR", "character": "CHAR", "text": "VARCHAR",
    "smallint": "SMALLINT", "integer": "INTEGER", "bigint": "BIGINT",
    "double precision": "DOUBLE PRECISION", "real": "REAL", "boolean": "BOOLEAN",
    "date": "DATE", "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMPTZ", "time without time zone": "TIME",
    "time with time zone": "TIMETZ", "super": "SUPER", "binary varying": "VARBYTE",
    "varbyte": "VARBYTE",
}
SUM_RTOL = 1e-9  # only for reporting sums in diagnoses (float sums depend on summation order)
_local = threading.local()


# ---------- rules ----------

def is_meta(column: str) -> bool:
    c = column.lower()
    return c.startswith("_airbyte") or c.startswith("_ab_") or c == "_id"


def q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def is_numeric(sql_type: str) -> bool:
    return sql_type.startswith("NUMERIC") or sql_type in INT_TYPES or sql_type in FLOAT_TYPES


def numeric_scale(sql_type: str) -> int:
    return int(sql_type.rstrip(")").split(",")[1]) if sql_type.startswith("NUMERIC(") else 0


def target(sql_type: str) -> str:
    """Cast target for reference type `sql_type`."""
    return "varchar(max)" if sql_type in TEXT_TYPES else sql_type.lower()


def canon(expr: str, sql_type: str) -> str:
    """SQL rendering `expr` (of type `sql_type`) as a fixed canonical string."""
    t = sql_type
    if t in TEXT_TYPES or t in INT_TYPES or t in ("TIME", "TIMETZ"):
        return f"({expr})::varchar(max)"
    if t.startswith("NUMERIC"):
        if numeric_scale(t) > 0:  # '123.450000000' -> '123.45', '100.000000000' -> '100'
            return f"rtrim(rtrim(({expr})::varchar(max), '0'), '.')"
        return f"({expr})::varchar(max)"
    if t in FLOAT_TYPES:
        return f"case when ({expr}) = 0 then '0' else ({expr})::varchar(max) end"
    if t == "BOOLEAN":
        return f"case when ({expr}) is null then null when ({expr}) then 'true' else 'false' end"
    if t == "DATE":
        return f"to_char({expr}, 'YYYY-MM-DD')"
    if t == "TIMESTAMP":
        return f"to_char({expr}, 'YYYY-MM-DD HH24:MI:SS.US')"
    if t == "TIMESTAMPTZ":
        return f"to_char(({expr}) at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS.US')"
    if t == "SUPER":
        # json_serialize turns NULL into 'null' and quotes strings; NULL and
        # JSON null stay NULL, strings render as their text (so a run column
        # holding the same text as VARCHAR matches).
        return (f"case when ({expr}) is null then null when is_varchar({expr}) "
                f"then ({expr})::varchar(max) else json_serialize({expr}) end")
    if t == "VARBYTE":
        return f"to_hex({expr})"
    return f"({expr})::varchar(max)"


def from_super(v: str, t: str) -> str:
    """Value of SUPER expression `v` as reference type `t` (JSON null -> NULL)."""
    if t == "SUPER":
        return v
    if t in TEXT_TYPES:
        return (f"case when {v} is null then null when is_varchar({v}) "
                f"then {v}::varchar(max) else json_serialize({v}) end")
    if is_numeric(t):
        return (f"case when json_typeof({v}) = 'number' then {v}::{target(t)} "
                f"when is_varchar({v}) then try_cast({v}::varchar(max) as {target(t)}) end")
    if t == "BOOLEAN":
        return (f"case when json_typeof({v}) = 'boolean' then {v}::boolean "
                f"when is_varchar({v}) then try_cast({v}::varchar(max) as boolean) end")
    return f"case when is_varchar({v}) then try_cast({v}::varchar(max) as {target(t)}) end"


def typed_run_expr(ref_type: str, column: str | None = None, run_type: str | None = None,
                   json_column: str | None = None, json_key: str | None = None) -> str:
    """Expression of the reference column's type, read from a run table."""
    t = ref_type
    if json_column is not None:  # lenient JSON mode
        return from_super(f"{q(json_column)}.{q(json_key)}", t)
    u = run_type
    if u == t:
        return q(column)
    if u == "SUPER":
        return from_super(q(column), t)
    if is_numeric(u) and is_numeric(t):
        return f"({q(column)})::{target(t)}"
    if t in TEXT_TYPES:
        return f"({q(column)})::varchar(max)"
    if t == "SUPER":
        # A string scalar: canon renders it as the same text a reference
        # string (or json_serialize of a reference object/number) has.
        return f"({q(column)})::varchar(max)::super"
    return f"try_cast(({q(column)})::varchar(max) as {target(t)})"


def stat_exprs(x: str, sql_type: str) -> list[tuple[str, str]]:
    """(name, SQL aggregate) summary statistics of typed expression `x`."""
    t = sql_type
    # md5: Redshift's DISTINCT ignores trailing blanks ('a' = 'a  '), md5 does not.
    out = [("non_null", f"count({x})"), ("distinct", f"count(distinct md5({canon(x, t)}))")]
    if is_numeric(t):
        out += [("min", canon(f"min({x})", t)), ("max", canon(f"max({x})", t)),
                ("sum", f"sum(({x})::double precision)")]
    elif t in TEXT_TYPES:
        out += [("min", f"left(min({x}), 100)"), ("max", f"left(max({x}), 100)"),
                ("total_length", f"sum(len({x})::bigint)")]
    elif t == "BOOLEAN":
        out += [("true", f"sum(case when {x} then 1 else 0 end)")]
    elif t == "SUPER":
        out += [("total_length", f"sum(len({canon(x, t)})::bigint)")]
    else:  # dates, times, timestamps, varbyte
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


def hash_num(h: str) -> str:
    """60-bit integer of hex hash column `h` ('N' = NULL counts as 1)."""
    return f"(case when {h} = 'N' then 1 else strtol(substring({h}, 1, 15), 16) end)::numeric(38,0)"


def table_stats_sql(source: str, exprs: list[str]) -> str:
    """Row count, table hash and one hash per column of canonical `exprs`."""
    cells = [f"coalesce(md5({e}), 'N') as h{i}" for i, e in enumerate(exprs)]
    hs = [f"h{i}" for i in range(len(exprs))]
    inner = f"select {', '.join(cells)} from {source}"
    mid = f"select {', '.join(hs)}, md5({' || '.join(hs)}) as rh from ({inner}) s"
    aggs = ["count(*)", f"coalesce(sum({hash_num('rh')}), 0)"]
    aggs += [f"coalesce(sum({hash_num(h)}), 0)" for h in hs]
    return f"select {', '.join(aggs)} from ({mid}) m"


# Columns per statistics query: Redshift Serverless cancels single queries
# with very many COUNT(DISTINCT ...) (e.g. 119 columns), so wide tables are
# summarized in slices.
STATS_COLUMNS_PER_QUERY = 10


def column_statistics(timer: "Timer", cur, source: str, columns: list[tuple[str, str, str]]):
    """[((name, stat), value)] for (name, typed expression, type) `columns`."""
    out = []
    for i in range(0, len(columns), STATS_COLUMNS_PER_QUERY):
        stats = [(c, k, sql) for c, x, ty in columns[i:i + STATS_COLUMNS_PER_QUERY]
                 for k, sql in stat_exprs(x, ty)]
        row = timer.run(cur, "column stats", f"select {', '.join(s for _, _, s in stats)} from {source}")[0]
        out += [((c, k), plain(v)) for (c, k, _), v in zip(stats, row)]
    return out


PROBE_COLUMNS = [  # (name, type)
    ("t", "VARCHAR"), ("n", "BIGINT"), ("d", "NUMERIC(38,9)"), ("f", "DOUBLE PRECISION"),
    ("b", "BOOLEAN"), ("dt", "DATE"), ("ts", "TIMESTAMP"), ("tz", "TIMESTAMPTZ"), ("v", "SUPER"),
]
PROBE_ROWS = [
    ["'Abc é'", "123", "123456789.123456789", "0.1", "true", "'2024-01-02'",
     "'2024-01-02 03:04:05.123456'", "'2024-01-02 03:04:05.5+02'", "json_parse('{\"b\":1,\"a\":[1,2.5,null]}')"],
    ["''", "-7", "-0.0000123", "1e20", "false", "'1970-01-01'",
     "'1970-01-01 00:00:00'", "'1999-12-31 23:59:59-05'", "json_parse('[\"x\",{\"k\":\"v\"}]')"],
    ["'f'", "0", "0", "-0.0", "null", "null", "null", "null", "json_parse('0.30000000000000004')"],
    ["null"] * 9,
]


def probe(cur) -> dict:
    selects = []
    for row in PROBE_ROWS:
        cols = []
        for (name, ty), lit in zip(PROBE_COLUMNS, row):
            cols.append(f"({lit})::super as {q(name)}" if ty == "SUPER" and lit == "null"
                        else f"{lit} as {q(name)}" if ty == "SUPER"
                        else f"({lit})::{target(ty)} as {q(name)}")
        selects.append("select " + ", ".join(cols))
    src = "(" + " union all ".join(selects) + ") p"
    exprs = [canon(q(name), ty) for name, ty in PROBE_COLUMNS]
    cur.execute(f"select {', '.join(exprs)} from {src} order by 1 nulls last")
    rendered = [list(r) for r in cur.fetchall()]
    cur.execute(table_stats_sql(src, exprs))
    row = cur.fetchone()
    return {"hash": str(row[1]), "rendered": rendered}


# ---------- connection / metadata ----------

def credentials(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return {"host": raw["host"], "port": int(raw["port"]),
            "user": raw.get("username") or raw["user"], "password": raw["password"]}


def cursor(creds: dict, database: str):
    if getattr(_local, "database", None) != database:
        # The socket timeout only matters when Redshift drops a session
        # without telling the client (seen with Serverless); queries
        # themselves take at most a few minutes.
        conn = redshift_connector.connect(database=database, timeout=1800, **creds)
        conn.autocommit = True
        cur = conn.cursor()
        for statement in SESSION_SETTINGS:
            cur.execute(statement)
        _local.conn, _local.cur, _local.database = conn, cur, database
    return _local.cur


def reset_cursor() -> None:
    conn = getattr(_local, "conn", None)
    _local.database = None
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def retrying(fn, *args, tries: int = 3):
    """Run fn(*args); on an error reconnect this thread and try again."""
    for attempt in range(1, tries + 1):
        try:
            return fn(*args)
        except Exception as exc:
            if attempt == tries:
                raise
            print(f"  retry {attempt}/{tries - 1} for {args}: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
            reset_cursor()
            time.sleep(10 * attempt)


def sql_type(data_type: str, precision, scale) -> str:
    if data_type == "numeric":
        return f"NUMERIC({precision},{scale})"
    return TYPE_NAMES.get(data_type, data_type.upper())


def columns_by_table(cur) -> dict:
    """{(schema, table_lower): (TableName, [(column, sql_type), ...])} of the connected database."""
    cur.execute(
        "select table_schema, table_name, column_name, data_type, numeric_precision, numeric_scale "
        "from information_schema.columns "
        "where table_schema not in ('information_schema', 'pg_catalog', 'airbyte_internal') "
        "order by table_schema, table_name, ordinal_position")
    out: dict = {}
    for s, t, c, ty, prec, scale in cur.fetchall():
        out.setdefault((s.lower(), t.lower()), (t, []))[1].append((c, sql_type(ty, prec, scale)))
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


# ---------- build ----------

def build(args) -> None:
    creds = credentials(args.credential)
    table_list = json.loads(args.table_json.read_text())
    t0 = time.perf_counter()
    cur = cursor(creds, args.reference_db)
    cur.execute("select version()")
    version = cur.fetchone()[0].rstrip("\x00")
    probe_value = probe(cur)
    meta = columns_by_table(cur)
    timer = Timer()

    def one(schema: str, table: str):
        name, cols = meta[(schema.lower(), table.lower())]
        fqn = f"{q(schema.lower())}.{q(name)}"
        data = sorted(((c, ty) for c, ty in cols if not is_meta(c)), key=lambda x: x[0].lower())
        exprs = [canon(q(c), ty) for c, ty in data]
        row = timer.run(cursor(creds, args.reference_db), "table hash", table_stats_sql(fqn, exprs))[0]
        n = len(data)
        column_stats: dict = collections.defaultdict(dict)
        for (c, k), v in column_statistics(timer, cursor(creds, args.reference_db), fqn,
                                           [(c, q(c), ty) for c, ty in data]):
            column_stats[c.lower()][k] = v
        return {"rows": row[0], "columns": [[c.lower(), ty] for c, ty in data], "hash": str(row[1]),
                "column_hashes": {c.lower(): str(h) for (c, _), h in zip(data, row[2:2 + n])},
                "column_stats": column_stats}

    jobs = [(s, t) for s in sorted(table_list) for t in table_list[s]]
    missing = [f"{s}.{t}" for s, t in jobs if (s.lower(), t.lower()) not in meta]
    if missing:
        raise SystemExit(f"{len(missing)} reference tables not in {args.reference_db}: {missing[:20]}")

    # Finished tables are saved as they complete, so a rerun after a failure
    # only computes the rest.
    partial_path = args.out.with_name(args.out.name + ".partial")
    key = {"rules_version": RULES_VERSION, "source_database": args.reference_db, "probe": probe_value["hash"]}
    done: dict = {}
    if partial_path.exists():
        saved = json.loads(partial_path.read_text())
        if saved.get("key") == key:
            done = {tuple(k.split("\t")): v for k, v in saved["tables"].items()}
            print(f"resuming: {len(done)} tables from {partial_path}", flush=True)
    lock = threading.Lock()

    def one_saved(schema: str, table: str):
        result = retrying(one, schema, table)
        with lock:
            done[(schema, table)] = result
            partial_path.write_text(json.dumps(
                {"key": key, "tables": {"\t".join(k): v for k, v in done.items()}}))
        return result

    todo = [job for job in jobs if job not in done]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {job: pool.submit(one_saved, *job) for job in todo}
    errors = []
    for job, f in futures.items():
        try:
            f.result()
        except Exception as exc:
            errors.append(f"{job[0]}.{job[1]}: {type(exc).__name__}: {str(exc)[:200]}")
    if errors:
        raise SystemExit(f"{len(errors)} tables failed (rerun to resume): " + "; ".join(errors[:10]))
    tables: dict = collections.defaultdict(dict)
    for s, t in jobs:
        tables[s][t] = done[(s, t)]
    elapsed = time.perf_counter() - t0
    out = {
        "warehouse": "redshift", "rules_version": RULES_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source_database": args.reference_db, "redshift_version": version,
        "notes": args.notes, "probe": probe_value, "tables": tables,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1))
    partial_path.unlink(missing_ok=True)
    print(f"built {args.out} from {args.reference_db}: {len(jobs)} tables in {len(tables)} tasks, "
          f"{elapsed:.1f}s ({args.workers} workers); probe hash {probe_value['hash']}")
    print(f"  {version}")
    for k, v in timer.summary().items():
        print(f"    {k:12s} {v['queries']:4d} queries, {v['total_s']:7.1f}s summed, mean {v['mean_s']:.3f}s, "
              f"max {v['max_s']:.2f}s")


# ---------- evaluate ----------

def evaluate(args) -> None:
    ref = json.loads(args.reference.read_text())
    if ref.get("warehouse") != "redshift":
        raise SystemExit(f"{args.reference} is a {ref.get('warehouse')} reference, not redshift")
    if ref.get("rules_version") != RULES_VERSION:
        raise SystemExit(f"reference rules_version {ref.get('rules_version')} != {RULES_VERSION}; rebuild it")
    creds = credentials(args.credential)
    timer = Timer()
    T0 = time.perf_counter()
    t = time.perf_counter()
    cur = cursor(creds, args.database)
    t_connect = time.perf_counter() - t
    t = time.perf_counter()
    now_probe = probe(cur)
    t_probe = time.perf_counter() - t
    if now_probe["hash"] != ref["probe"]["hash"]:
        changed = [(a, b) for a, b in zip(ref["probe"]["rendered"], now_probe["rendered"]) if a != b]
        raise SystemExit("probe hash changed: hashing or formatting differs from when the reference was built "
                         f"(rendering differences: {changed or 'none, hash function changed'}). Rebuild the reference.")
    t = time.perf_counter()
    run_meta = columns_by_table(cur)
    t_meta = time.perf_counter() - t
    schemas = sorted(ref["tables"])
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        schemas = [s for s in schemas if s in wanted]

    def one(schema: str, table: str) -> dict:
        r = ref["tables"][schema][table]
        names = [c for c, _ in r["columns"]]
        found = run_meta.get((schema.lower(), table.lower()))
        if found is None:
            return {"status": "missing_in_run", "reference_rows": r["rows"],
                    "columns_total": len(names), "columns_matching": 0}
        name, cols = found
        fqn = f"{q(schema.lower())}.{q(name)}"
        run_cols = {c.lower(): (c, ty) for c, ty in cols if not is_meta(c)}
        typed, missing, extracted = {}, [], []
        json_cols = [c for c, ty in run_cols.values() if ty == "SUPER" and c.lower() == "data"]
        keys = None
        for col, ref_type in r["columns"]:
            if col in run_cols:
                c, ty = run_cols[col]
                typed[col] = typed_run_expr(ref_type, column=c, run_type=ty)
                continue
            if json_cols and keys is None:
                rows = timer.run(cursor(creds, args.database), "json keys",
                                 f"select distinct k from {fqn} r, unpivot r.{q(json_cols[0])} as v at k")
                keys = {}
                for (k,) in rows:
                    keys.setdefault(k.lower(), k)
            if keys and col in keys:
                typed[col] = typed_run_expr(ref_type, json_column=json_cols[0], json_key=keys[col])
                extracted.append(col)
            else:
                missing.append(col)
        exprs = [canon(typed[c], ty) if c in typed else "null::varchar" for c, ty in r["columns"]]
        row = timer.run(cursor(creds, args.database), "table stats", table_stats_sql(fqn, exprs))[0]
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
            diagnosis: dict = collections.defaultdict(dict)
            for (c, k), v in column_statistics(timer, cursor(creds, args.database), fqn,
                                               [(c, typed[c], types[c]) for c in differing]):
                want = r["column_stats"][c][k]
                if stat_differs(k, want, v):
                    diagnosis[c][k] = [want, v]
            res["diagnosis"] = {c: diagnosis.get(c) or "values differ; counts, min/max and sums agree"
                                for c in differing}
        return res

    jobs = [(s, tb) for s in schemas for tb in ref["tables"][s]]
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {job: pool.submit(retrying, one, *job) for job in jobs}
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
        {"warehouse": "redshift", "database": args.database, "reference": str(args.reference),
         "rules_version": RULES_VERSION, "reference_generated_at": ref["generated_at"], "timing": timing,
         "summary": summary, "tasks_passed": summary["tasks"]["passed"], "tasks": tasks, "tables": results},
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
    common.add_argument("--credential", type=Path, default=PROJECT_DIR / "setup/destination/redshift_credential.json")
    common.add_argument("--workers", type=int, default=8)
    b = sub.add_parser("build", parents=[common])
    b.add_argument("--reference-db", required=True)
    b.add_argument("--table-json", type=Path, default=EVALUATION_DIR / "table.json")
    b.add_argument("--out", type=Path, default=REFERENCE_DIR / "redshift.json")
    b.add_argument("--notes", default="")
    e = sub.add_parser("evaluate", parents=[common])
    e.add_argument("--database", required=True)
    e.add_argument("--folder", required=True)
    e.add_argument("--reference", type=Path, default=REFERENCE_DIR / "redshift.json")
    e.add_argument("--only", default="")
    args = p.parse_args()
    build(args) if args.cmd == "build" else evaluate(args)


if __name__ == "__main__":
    main()
