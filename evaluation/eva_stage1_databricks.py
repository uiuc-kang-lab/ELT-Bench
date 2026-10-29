"""Stage-1 (extraction and loading) content check for Databricks, with reference values computed on Databricks.

The reference is built from a ground-truth catalog (default `elt`) for the source tables listed in the Snowflake
reference (evaluation/stage1_reference/snowflake.json, 835 tables). Values are never compared across warehouses:
Databricks runs are checked only against this Databricks reference.

Per table: row count, an order-independent multiset hash of canonical rows (sum of xxhash64 as DECIMAL(38,0)),
one such hash per column (diagnosis), and per-column statistics (diagnosis, and to cross-check the reference
against the Snowflake reference). Ignored columns: _airbyte_*, _ab_*, and MongoDB _id.

Canonical values (type of the reference column; run columns are converted to it first)
  string               the value
  tinyint..bigint      decimal digits
  decimal(p,s)         cast to string (fixed scale s)
  double / float       15 significant digits, '%.14E' (0 -> '0', NaN / Infinity spelled out)
  boolean              'true' / 'false'
  date                 yyyy-MM-dd
  timestamp            UTC, yyyy-MM-dd HH:mm:ss.SSSSSS (session time zone set to UTC)
  timestamp_ntz        yyyy-MM-dd HH:mm:ss.SSSSSS
  array/map/struct/variant  to_json
  NULL                 a sentinel distinct from every string

The reference (stage1_reference/databricks.json) was built from catalog `elt`; the 9 tables loaded there before the
2026-10 loader fixes come from catalog `elt_gt_reload` (see the reference's "notes").

usage: eva_stage1_databricks.py build [--catalog elt] [--tables task.table,...] [--ref PATH]
       eva_stage1_databricks.py evaluate --catalog CATALOG --folder RESULT_FOLDER [--only a,b] [--ref PATH]
       eva_stage1_databricks.py crosscheck [--ref PATH]
evaluate writes agent_results/<folder>/stage1_stored.{json,log} (results.log-style lines).
"""
import argparse, decimal, json, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
SF_REF = EVALUATION_DIR / "stage1_reference" / "snowflake.json"
DEFAULT_REF = EVALUATION_DIR / "stage1_reference" / "databricks.json"
CREDENTIAL = EVALUATION_DIR.parent / "setup" / "destination" / "databricks_credential.json"
NULL = "concat(chr(0), 'N')"  # sentinel for NULL inside hashes
SUM_RTOL = 1e-9
_local = threading.local()


def connect():
    from databricks import sql
    from databricks.sdk.core import Config, oauth_service_principal
    c = json.loads(CREDENTIAL.read_text())
    host = str(c["hostname"]).removeprefix("https://")
    cfg = Config(host=f"https://{host}", client_id=c["client_id"], client_secret=c["secret"])
    conn = sql.connect(server_hostname=host, http_path=c["http_path"],
                       credentials_provider=lambda: oauth_service_principal(cfg))
    cur = conn.cursor()
    cur.execute("SET TIME ZONE 'UTC'")
    return conn, cur


def cursor():
    if not hasattr(_local, "cur"):
        _local.conn, _local.cur = connect()
    return _local.cur


def q(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def is_meta(col: str) -> bool:
    c = col.lower()
    return c.startswith("_airbyte_") or c.startswith("_ab_") or c == "_id"


def base(t: str) -> str:
    return t.lower().split("(")[0].split("<")[0].strip()


INTS = {"tinyint", "smallint", "int", "integer", "bigint", "long", "byte", "short"}
FLOATS = {"double", "float", "real"}
COMPLEX = {"array", "map", "struct", "variant"}


def is_numeric(t: str) -> bool:
    return base(t) in INTS | FLOATS | {"decimal", "numeric"}


def canon(x: str, t: str) -> str:
    b = base(t)
    if b == "string" or b.startswith("varchar") or b.startswith("char"):
        return f"({x})"
    if b in INTS or b in ("decimal", "numeric"):
        return f"cast({x} as string)"
    if b in FLOATS:
        d = f"cast({x} as double)"
        return (f"case when {d} is null then null when {d} = 0 then '0' when isnan({d}) then 'NaN' "
                f"when {d} = double('inf') then 'Infinity' when {d} = double('-inf') then '-Infinity' "
                f"else format_string('%.14E', {d}) end")
    if b == "boolean":
        return f"case when ({x}) then 'true' when not ({x}) then 'false' end"
    if b == "date":
        return f"date_format({x}, 'yyyy-MM-dd')"
    if b in ("timestamp", "timestamp_ltz", "timestamp_ntz"):
        return f"date_format({x}, 'yyyy-MM-dd HH:mm:ss.SSSSSS')"
    if b in COMPLEX:
        return f"to_json({x})"
    if b == "binary":
        return f"hex({x})"
    if b in ("void", "null"):
        return "cast(null as string)"
    return f"cast({x} as string)"


def typed_run_expr(ref_type: str, column=None, run_type=None, json_column=None, json_key=None) -> str:
    """Expression of the reference column's type, read from a run table (or extracted from a JSON column)."""
    if json_column is not None:  # lenient JSON mode (MongoDB collection loaded as one JSON column)
        v = f"get_json_object(cast({q(json_column)} as string), '$.{json_key}')"
        return v if base(ref_type) == "string" else f"try_cast({v} as {ref_type})"
    if run_type.lower() == ref_type.lower():
        return q(column)
    if base(ref_type) in ("void", "null"):
        return "cast(null as string)"
    if is_numeric(run_type) and is_numeric(ref_type):
        return f"cast({q(column)} as {ref_type})"
    if base(ref_type) == "string":
        if base(run_type) in COMPLEX:
            return f"to_json({q(column)})"
        return f"cast({q(column)} as string)"
    if base(ref_type) in COMPLEX:
        return f"cast({q(column)} as string)"  # compared as JSON text
    return f"try_cast(cast({q(column)} as string) as {ref_type})"


def stat_exprs(x: str, t: str):
    b = base(t)
    out = [("non_null", f"count({x})"), ("distinct", f"count(distinct {canon(x, t)})")]
    if is_numeric(t):
        out += [("min", canon(f"min({x})", t)), ("max", canon(f"max({x})", t)), ("sum", f"sum(cast({x} as double))")]
    elif b == "string":
        out += [("min", f"left(min({x}), 100)"), ("max", f"left(max({x}), 100)"), ("total_length", f"sum(length({x}))")]
    elif b == "boolean":
        out += [("true", f"count_if({x})")]
    elif b in COMPLEX:
        out += [("total_length", f"sum(length(to_json({x})))")]
    else:
        out += [("min", canon(f"min({x})", t)), ("max", canon(f"max({x})", t))]
    return out


def hash_sql(exprs):
    """exprs: canonical string expressions -> (row hash, per-column hashes)."""
    args = ", ".join(f"coalesce({e}, {NULL})" for e in exprs) or "''"
    row = f"sum(cast(xxhash64({args}) as decimal(38,0)))"
    cols = [f"sum(cast(xxhash64(coalesce({e}, {NULL})) as decimal(38,0)))" for e in exprs]
    return row, cols


def columns_by_table(cur, catalog: str):
    cur.execute(f"select lower(table_schema), lower(table_name), table_name, column_name, full_data_type, ordinal_position "
                f"from {q(catalog)}.information_schema.columns where table_schema <> 'information_schema'")
    out = {}
    for s, t, tname, c, ty, pos in sorted(cur.fetchall(), key=lambda r: (r[0], r[1], r[5])):
        out.setdefault((s, t), (tname, []))[1].append((c, ty))
    return out


def plain(v):
    if isinstance(v, decimal.Decimal):
        return str(v) if v == v.to_integral_value() else float(v)
    return v


def ref_tables():
    sf = json.loads(SF_REF.read_text())
    return sorted((task, tb) for task, tabs in sf["tables"].items() for tb in tabs)


def build_one(catalog, meta, task, table):
    tname, cols = meta[(task, table.lower())]
    cols = [(c, ty) for c, ty in cols if not is_meta(c)]
    fqn = f"{q(catalog)}.{q(task)}.{q(tname)}"
    exprs = [canon(q(c), ty) for c, ty in cols]
    row, colh = hash_sql(exprs)
    stats = [(c, name, e) for c, ty in cols for name, e in stat_exprs(q(c), ty)]
    sel = ", ".join(["count(*)", row] + colh + [e for _, _, e in stats])
    cur = cursor()
    t0 = time.perf_counter()
    cur.execute(f"select {sel} from {fqn}")
    r = cur.fetchone()
    secs = time.perf_counter() - t0
    n = len(cols)
    cstats = {}
    for (c, name, _), v in zip(stats, r[2 + n:]):
        cstats.setdefault(c.upper(), {})[name] = plain(v)
    return {"rows": r[0], "columns": [[c.upper(), ty] for c, ty in cols], "hash": str(r[1]),
            "column_hashes": {c.upper(): str(h) for (c, _), h in zip(cols, r[2:2 + n])},
            "column_stats": cstats, "seconds": round(secs, 2)}


def build(catalog, out, only=None, workers=4):
    _, cur = connect()
    meta = columns_by_table(cur, catalog)
    todo = [(t, tb) for t, tb in ref_tables() if not only or f"{t}.{tb}" in only]
    res = json.loads(out.read_text()) if out.exists() and only else {"tables": {}}
    missing = [f"{t}.{tb}" for t, tb in todo if (t, tb.lower()) not in meta]
    todo = [x for x in todo if (x[0], x[1].lower()) in meta]

    def one(x):
        t, tb = x
        try:
            return t, tb, build_one(catalog, meta, t, tb)
        except Exception as ex:
            return t, tb, {"error": f"{type(ex).__name__}: {str(ex)[:300]}"}
    t0 = time.time()
    with ThreadPoolExecutor(workers) as pool:
        for i, (t, tb, r) in enumerate(pool.map(one, todo), 1):
            res["tables"].setdefault(t, {})[tb] = r
            if "error" in r or i % 50 == 0:
                print(f"[{i}/{len(todo)}] {t}.{tb} {r.get('error', '')}", flush=True)
    res.update(warehouse="databricks", source_catalog=catalog, generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
               rules="canonical values per eva_stage1_databricks.py docstring; hash = sum(xxhash64) as decimal(38,0)",
               missing=missing, build_seconds=round(time.time() - t0, 1))
    out.write_text(json.dumps(res, indent=1, sort_keys=True))
    print(f"built {len(todo)} tables in {res['build_seconds']} s; missing {missing}")


# ---------------- cross-check against the Snowflake reference (statistics only) ----------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ts(v):  # '2021-04-01 19:42:58.123000000' -> '2021-04-01 19:42:58.123000'
    return v[:26] if isinstance(v, str) and re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+$", v) else v


def crosscheck(ref_path):
    db = json.loads(Path(ref_path).read_text())["tables"]
    sf = json.loads(SF_REF.read_text())["tables"]
    report = {"tables": 0, "rows_differ": [], "columns_missing": [], "columns_extra": [], "stat_differs": [], "type_pairs": {}}
    for task, tabs in sf.items():
        for tb, s in tabs.items():
            d = db.get(task, {}).get(tb)
            if not d or "error" in d:
                report["rows_differ"].append((f"{task}.{tb}", s["rows"], None)); continue
            report["tables"] += 1
            if d["rows"] != s["rows"]:
                report["rows_differ"].append((f"{task}.{tb}", s["rows"], d["rows"]))
            st = dict(s["columns"]); dt = dict(d["columns"])
            report["columns_missing"] += [f"{task}.{tb}.{c}" for c in st if c not in dt]
            report["columns_extra"] += [f"{task}.{tb}.{c}" for c in dt if c not in st]
            for c in st:
                if c not in dt:
                    continue
                pair = f"{st[c].split('(')[0]} -> {base(dt[c])}"
                report["type_pairs"][pair] = report["type_pairs"].get(pair, 0) + 1
                a, b = s["column_stats"].get(c, {}), d["column_stats"].get(c, {})
                diffs = []
                for k in ("non_null", "distinct", "total_length", "true"):
                    if k in a and k in b and a[k] != b[k] and not (k == "total_length" and st[c] == "VARIANT"):
                        diffs.append((k, a[k], b[k]))
                if "sum" in a and "sum" in b and a["sum"] is not None and b["sum"] is not None:
                    if abs(a["sum"] - b["sum"]) > SUM_RTOL * max(abs(a["sum"]), abs(b["sum"])) + 1e-12:
                        diffs.append(("sum", a["sum"], b["sum"]))
                for k in ("min", "max"):
                    if k in a and k in b:
                        x, y = _num(a[k]), _num(b[k])
                        if x is not None and y is not None:
                            if abs(x - y) > 1e-9 * max(abs(x), abs(y)) + 1e-12:
                                diffs.append((k, a[k], b[k]))
                        elif _ts(a[k]) != _ts(b[k]) and not (st[c] == "TEXT" and base(dt[c]) == "string" and False):
                            diffs.append((k, a[k], b[k]))
                if diffs:
                    report["stat_differs"].append((f"{task}.{tb}.{c}", st[c], dt[c], diffs))
    return report


# ---------------- evaluate an agent catalog ----------------
def eval_one(catalog, meta, ref, task, table):
    r = ref["tables"][task][table]
    names = [c for c, _ in r["columns"]]
    found = meta.get((task, table.lower()))
    if found is None:
        return {"status": "missing_in_run", "reference_rows": r["rows"], "columns_total": len(names), "columns_matching": 0}
    tname, cols = found
    fqn = f"{q(catalog)}.{q(task)}.{q(tname)}"
    run_cols = {c.upper(): (c, ty) for c, ty in cols if not is_meta(c)}
    json_cols = [c for c, ty in run_cols.values() if c.upper() == "DATA" and base(ty) in ("string", "variant")]
    cur = cursor()
    typed, missing, extracted, keys = {}, [], [], None
    for col, rtype in r["columns"]:
        if col in run_cols:
            c, ty = run_cols[col]
            typed[col] = typed_run_expr(rtype, column=c, run_type=ty)
            continue
        if json_cols and keys is None:
            cur.execute(f"select distinct k from (select explode(json_object_keys(cast({q(json_cols[0])} as string))) k from {fqn})")
            keys = {k.upper(): k for (k,) in cur.fetchall() if k is not None}
        if keys and col in keys:
            typed[col] = typed_run_expr(rtype, json_column=json_cols[0], json_key=keys[col].replace("'", "\\'"))
            extracted.append(col)
        else:
            missing.append(col)
    exprs = [canon(typed[c], ty) if c in typed else "cast(null as string)" for c, ty in r["columns"]]
    row, colh = hash_sql(exprs)
    cur.execute(f"select count(*), {row}, {', '.join(colh)} from {fqn}")
    got = cur.fetchone()
    matching = [c for c, h in zip(names, got[2:]) if c in typed and str(h) == r["column_hashes"][c]]
    differing = [c for c in names if c in typed and c not in matching]
    res = {"reference_rows": r["rows"], "run_rows": got[0], "columns_total": len(names), "columns_matching": len(matching)}
    if differing:
        res["differing_columns"] = differing
    if missing:
        res["missing_columns"] = missing
    if extracted:
        res["extracted_from_json"] = extracted
    extra = sorted(set(run_cols) - set(names))
    if extra:
        res["only_in_run"] = extra
    if str(got[1]) == r["hash"] and not missing:
        res["status"] = "identical_via_json" if extracted else "identical"
        return res
    res["status"] = "different"
    if not differing and not missing and got[0] == r["rows"]:
        res["note"] = "rows misaligned: each column's values match, their combination per row does not"
    if differing:  # explain each differing column with the stored statistics
        types = dict(r["columns"])
        stats = [(c, k, e) for c in differing for k, e in stat_exprs(typed[c], types[c])]
        cur.execute(f"select {', '.join(e for _, _, e in stats)} from {fqn}")
        vals = cur.fetchone()
        diag = {}
        for (c, k, _), v in zip(stats, vals):
            want, have = r["column_stats"].get(c, {}).get(k), plain(v)
            if k == "sum" and want is not None and have is not None:
                if abs(want - have) <= SUM_RTOL * max(abs(want), abs(have)) + 1e-12:
                    continue
            elif want == have:
                continue
            diag.setdefault(c, {})[k] = [want, have]
        res["diagnosis"] = {c: diag.get(c) or "values differ; counts, min/max and sums agree" for c in differing}
    return res


def evaluate(catalog, ref_path, folder, tasks=None, workers=4):
    import collections
    ref = json.loads(Path(ref_path).read_text())
    T0 = time.time()
    _, cur = connect()
    meta = columns_by_table(cur, catalog)
    present = {s for s, _ in meta}
    schemas = sorted(t for t in ref["tables"] if (not tasks or t in tasks))
    if not tasks:  # only the tasks this run contains (reruns cover a subset)
        schemas = [s for s in schemas if s in present]
    jobs = [(s, tb) for s in schemas for tb in ref["tables"][s]]

    def one(job):
        try:
            return job, eval_one(catalog, meta, ref, *job)
        except Exception as ex:
            return job, {"status": "error", "error": f"{type(ex).__name__}: {str(ex)[:300]}",
                         "columns_total": len(ref["tables"][job[0]][job[1]]["columns"]), "columns_matching": 0}
    results = collections.defaultdict(dict)
    with ThreadPoolExecutor(workers) as pool:
        for (s, tb), r in pool.map(one, jobs):
            results[s][tb] = r
    passing = ("identical", "identical_via_json")
    rows_ok = lambda r: r.get("run_rows") is not None and r["run_rows"] == r.get("reference_rows")
    task_res = {s: {"passed": all(r["status"] in passing for r in results[s].values()),
                    "row_counts_match": all(rows_ok(r) for r in results[s].values())} for s in schemas}
    every = [r for v in results.values() for r in v.values()]
    summary = {"tasks": {"total": len(schemas), "passed": sum(x["passed"] for x in task_res.values()),
                         "row_counts_match": sum(x["row_counts_match"] for x in task_res.values())},
               "tables": {"total": len(every), "present": sum(r["status"] != "missing_in_run" for r in every),
                          "row_counts_match": sum(rows_ok(r) for r in every),
                          "identical": sum(r["status"] in passing for r in every)},
               "seconds": round(time.time() - T0, 1)}
    out_dir = EVALUATION_DIR / "agent_results" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "stage1_stored.json"
    out.write_text(json.dumps({"catalog": catalog, "reference": str(ref_path), "summary": summary,
                                     "tasks": task_res, "tables": results}, indent=1, default=str))
    with open(out.with_suffix(".log"), "w") as log:
        for s in schemas:
            bad = {tb: r["status"] for tb, r in results[s].items() if r["status"] not in passing}
            log.write(f"Success: {s} content verified\n" if task_res[s]["passed"] else f"Error: {s} {json.dumps(bad)}\n")
    st = collections.Counter(r["status"] for r in every)
    print(f"{catalog}: tasks passed {summary['tasks']['passed']}/{len(schemas)} (row counts match {summary['tasks']['row_counts_match']}) | "
          f"tables identical {summary['tables']['identical']}/{len(every)}, row counts {summary['tables']['row_counts_match']} | "
          f"{dict(st)} | {summary['seconds']} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "crosscheck", "evaluate"])
    ap.add_argument("--catalog", default="elt")
    ap.add_argument("--tables", default="", help="build: only these task.table entries (merged into --ref)")
    ap.add_argument("--only", default="", help="evaluate: comma-separated tasks (default: every task in the catalog)")
    ap.add_argument("--folder", help="evaluate: result folder under evaluation/agent_results")
    ap.add_argument("--ref", default=str(DEFAULT_REF))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.catalog, Path(a.ref), {x for x in a.tables.split(",") if x}, a.workers)
    elif a.cmd == "evaluate":
        if not a.folder:
            ap.error("evaluate needs --folder")
        evaluate(a.catalog, a.ref, a.folder, {x for x in a.only.split(",") if x}, a.workers)
    else:
        r = crosscheck(a.ref)
        Path(a.ref).with_suffix(".crosscheck.json").write_text(json.dumps(r, indent=1, default=str))
        print(f"tables {r['tables']} | rows differ {len(r['rows_differ'])} | columns missing {len(r['columns_missing'])} "
              f"extra {len(r['columns_extra'])} | columns with differing stats {len(r['stat_differs'])}")
        print("type pairs:", r["type_pairs"])


if __name__ == "__main__":
    main()
