"""Content-level stage-1 check (Snowflake).

Stage 1 (eva_stage1.py) only compares row counts. This script compares the
*contents* of every loaded source table in a run's database against a
reference database (e.g. ELT_STAGE1_REF, a zero-copy clone of a run that
passed stage 1), entirely inside Snowflake:

  * Airbyte metadata columns (_AIRBYTE_*, and _AB_* such as CDC cursors and
    _AB_SOURCE_FILE_LAST_MODIFIED) and MongoDB's internal _ID are ignored —
    they differ per sync/upload or are not part of any task schema;
  * lenient JSON mode: when a run loaded a table as one JSON column (e.g. the
    MongoDB source with schema_enforced = false gives _ID + DATA), reference
    columns missing from the run are extracted from that column by key
    (case-insensitive) and cast to the reference column's type;
  * columns are matched case-insensitively; missing/extra columns and type
    differences are reported;
  * contents are compared with an order-independent HASH_AGG over the common
    columns cast to VARCHAR; for tables whose hashes differ, per-column hashes
    name the differing columns and EXCEPT counts the rows found on one side
    only.

The reference is not ground truth: a difference means "differs from the
reference load", which may come from either side.

Usage:
    python eva_stage1_content.py --database codex_gpt6astra \
        --reference elt_stage1_ref --folder codex-cli-gpt-6-astra
Writes agent_results/<folder>/stage1_content.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import snowflake.connector

EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVALUATION_DIR.parent
_local = threading.local()


def _cursor(creds: dict):
    if not hasattr(_local, "cur"):
        _local.conn = snowflake.connector.connect(login_timeout=60, **creds)
        _local.cur = _local.conn.cursor()
    return _local.cur


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _metadata(creds: dict, database: str):
    """{SCHEMA: {table_lower: (TableName, row_count, [(col, type), ...])}}."""
    cur = _cursor(creds)
    db = _q(database.upper())
    cur.execute(f"select table_schema, table_name, row_count from {db}.information_schema.tables "
                "where table_type = 'BASE TABLE' and table_schema <> 'INFORMATION_SCHEMA'")
    tables = {(s, t): rc for s, t, rc in cur.fetchall()}
    cur.execute(f"select table_schema, table_name, column_name, data_type, numeric_precision, numeric_scale "
                f"from {db}.information_schema.columns "
                "where table_schema <> 'INFORMATION_SCHEMA' order by table_schema, table_name, ordinal_position")
    cols = collections.defaultdict(list)
    for s, t, c, ty, prec, scale in cur.fetchall():
        sql_type = f"NUMBER({prec},{scale})" if ty == "NUMBER" and prec is not None else ty
        cols[(s, t)].append((c, sql_type))
    meta = collections.defaultdict(dict)
    for (s, t), rc in tables.items():
        meta[s][t.lower()] = (t, rc, cols.get((s, t), []))
    return meta


def _is_meta(column: str) -> bool:
    # _ID is MongoDB's internal document id: no task schema (inputs/*/schemas)
    # lists it, so a run that does not sync it has not lost task data.
    c = column.upper()
    return c.startswith("_AIRBYTE") or c.startswith("_AB_") or c == "_ID"


JSON_TYPES = ("VARIANT", "OBJECT")


def _json_extract_expr(json_col: str, key: str, ref_type: str) -> str:
    """Value of `key` in a JSON column, shaped like the reference column."""
    v = f"to_varchar(strip_null_value({_q(json_col)}:{_q(key)}))"
    if ref_type in ("TEXT", "VARCHAR") or ref_type in JSON_TYPES:
        return v
    return f"to_varchar(try_cast({v} as {ref_type}))"


def _compare(creds, run_db, ref_db, schema, table, run_meta, ref_meta) -> dict:
    s = schema.upper()
    ref = ref_meta.get(s, {}).get(table.lower())
    run = run_meta.get(s, {}).get(table.lower())
    if ref is None:
        return {"status": "missing_in_reference"}
    if run is None:
        return {"status": "missing_in_run"}
    ref_name, ref_rows, ref_cols = ref
    run_name, run_rows, run_cols = run
    data = lambda cols: {c.upper(): (c, ty) for c, ty in cols if not _is_meta(c)}
    rc, uc = data(ref_cols), data(run_cols)
    cur = _cursor(creds)
    fqn = lambda db, name: f"{_q(db.upper())}.{_q(s)}.{_q(name)}"
    # Per reference column: (reference expression, run expression).
    exprs = {k: (f"to_varchar({_q(rc[k][0])})", f"to_varchar({_q(uc[k][0])})") for k in rc if k in uc}
    extracted = []
    missing = [k for k in rc if k not in uc]
    json_cols = [c for c, ty in uc.values() if ty in JSON_TYPES and c.upper() == "DATA"]
    if missing and json_cols:
        jc = json_cols[0]
        cur.execute(f"select distinct f.key from {fqn(run_db, run_name)} r, lateral flatten(input => r.{_q(jc)}) f")
        keys = {k.upper(): k for (k,) in cur.fetchall()}
        for k in missing:
            if k in keys:
                exprs[k] = (f"to_varchar({_q(rc[k][0])})", _json_extract_expr(jc, keys[k], rc[k][1]))
                extracted.append(k)
    common = [k for k in rc if k in exprs]  # reference column order
    res = {
        "reference_rows": ref_rows, "run_rows": run_rows,
        "only_in_reference": sorted(set(rc) - set(common)),
        "only_in_run": sorted(set(uc) - set(rc)),
        "type_differences": {k: [rc[k][1], uc[k][1]] for k in common if k in uc and rc[k][1] != uc[k][1]},
    }
    if extracted:
        res["extracted_from_json"] = sorted(extracted)
    if not common:
        res["status"] = "no_common_columns"
        return res
    side = {"ref": 0, "run": 1}
    cols_sql = lambda which: ", ".join(exprs[k][side[which]] for k in common)
    hashes = []
    for which, db, name in (("ref", ref_db, ref_name), ("run", run_db, run_name)):
        cur.execute(f"select count(*), hash_agg({cols_sql(which)}) from {fqn(db, name)}")
        hashes.append(cur.fetchone())
    res["reference_rows"], res["run_rows"] = hashes[0][0], hashes[1][0]
    same = hashes[0][1] == hashes[1][1]
    res["content_identical"] = same
    if same:
        # Columns only the run has (e.g. the JSON column itself) do not count.
        if res["only_in_reference"]:
            res["status"] = "identical_common_columns"
        else:
            res["status"] = "identical_via_json" if extracted else "identical"
        return res
    # Diagnose: which columns differ, and how many rows exist on one side only.
    per_col = []
    for which, db, name in (("ref", ref_db, ref_name), ("run", run_db, run_name)):
        cur.execute("select " + ", ".join(f"hash_agg({exprs[k][side[which]]})" for k in common)
                    + f" from {fqn(db, name)}")
        per_col.append(cur.fetchone())
    res["differing_columns"] = [k for k, a, b in zip(common, *per_col) if a != b]
    sel = lambda which, db, name: f"select {cols_sql(which)} from {fqn(db, name)}"
    cur.execute(f"select count(*) from ({sel('run', run_db, run_name)} except {sel('ref', ref_db, ref_name)})")
    res["rows_only_in_run"] = cur.fetchone()[0]
    cur.execute(f"select count(*) from ({sel('ref', ref_db, ref_name)} except {sel('run', run_db, run_name)})")
    res["rows_only_in_reference"] = cur.fetchone()[0]
    res["status"] = "different"
    return res


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", required=True, help="Run database to check")
    p.add_argument("--reference", default="elt_stage1_ref", help="Reference database")
    p.add_argument("--folder", required=True, help="agent_results subfolder for the output")
    p.add_argument("--credential", type=Path,
                   default=PROJECT_DIR / "setup/destination/snowflake_credential.json")
    p.add_argument("--table-json", type=Path, default=EVALUATION_DIR / "table.json")
    p.add_argument("--only", default="", help="Comma-separated task schemas")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    raw = json.loads(args.credential.read_text())
    creds = {k: raw[k] for k in ("account", "user", "password", "role", "warehouse") if raw.get(k)}
    table_list = json.loads(args.table_json.read_text())
    schemas = sorted(table_list)
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        schemas = [s for s in schemas if s in wanted]

    t0 = time.perf_counter()
    ref_meta, run_meta = _metadata(creds, args.reference), _metadata(creds, args.database)
    jobs = [(s, t) for s in schemas for t in table_list[s]]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {job: pool.submit(_compare, creds, args.database, args.reference, *job, run_meta, ref_meta)
                   for job in jobs}
    results = collections.defaultdict(dict)
    for (s, t), fut in futures.items():
        try:
            results[s][t] = fut.result()
        except Exception as e:  # keep going; report the failure
            results[s][t] = {"status": "error", "error": str(e)[:500]}
    elapsed = time.perf_counter() - t0

    out_dir = EVALUATION_DIR / "agent_results" / args.folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {"database": args.database, "reference": args.reference,
           "elapsed_seconds": round(elapsed, 1), "tables": results}
    (out_dir / "stage1_content.json").write_text(json.dumps(out, indent=2, default=str))

    statuses = collections.Counter(r["status"] for v in results.values() for r in v.values())
    passing = ("identical", "identical_via_json")
    tasks_ok = sum(1 for v in results.values() if all(r["status"] in passing for r in v.values()))
    print(f"{args.database} vs {args.reference}: {len(jobs)} tables in {len(schemas)} tasks, {elapsed:.1f}s")
    print(f"  tables by status: {dict(statuses)}")
    print(f"  tasks with every table identical: {tasks_ok}/{len(schemas)}")
    for s, v in sorted(results.items()):
        for t, r in sorted(v.items()):
            if r["status"] != "identical":
                extra = {k: r[k] for k in ("reference_rows", "run_rows", "differing_columns", "rows_only_in_run",
                                           "rows_only_in_reference", "only_in_reference", "only_in_run",
                                           "type_differences", "error") if r.get(k)}
                print(f"  {s}.{t}: {r['status']} {json.dumps(extra, default=str)[:400]}")
    print(f"Wrote {out_dir / 'stage1_content.json'}")


if __name__ == "__main__":
    main()
