"""Mutation testing of the stage-2 verifier on a sample of data models.

For each sampled data model, the ground-truth query (dbt-compiled, reading the
GT source data and the GT intermediate models in Snowflake) is mutated with
the operators in mutate.py. The original and every mutant are materialized as
MUTATION_TEST.<task>.<model> and graded exactly like an agent's table
(eva_stage2: evaluation SQL or full table, CSV round trip, sort by key,
check_corretness against the ground-truth CSV). Each mutant is classified:

  invalid     the mutant fails to run
  equivalent  its output equals the original query's output (any output-based
              grader must accept it)
  killed      its output differs and the verifier rejects it
  survived    its output differs but the verifier accepts it (a false pass)

    python run.py --sample 20 --seed 20261014

sqlglot (27.8.0) is imported from .pylib when present:
    pip install --target evaluation/mutation_testing/.pylib sqlglot==27.8.0
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".pylib"))
sys.path.insert(0, str(HERE))
EVAL = HERE.parent
sys.path.insert(0, str(EVAL))
os.chdir(EVAL)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import mutate  # noqa: E402
from db_connectors import get_connector  # noqa: E402
from eva_stage2 import check_corretness, sort_by_keys, table_keys  # noqa: E402

PROJECT = EVAL.parent
GT_CSV = PROJECT / "ground_truth/gt_snowflake"
REBUILD = Path("/mydata/elt/ELT_GT_v5/dbt_gt_rebuild")
CREDENTIAL = PROJECT / "setup/destination/snowflake_credential.json"
DATABASE = "MUTATION_TEST"
OUT = EVAL / "agent_results/_mutation"
STATEMENT_TIMEOUT_SEC = 600

_lock = threading.Lock()


def compiled_sql(task: str, model: str) -> str:
    for path in glob.glob(str(REBUILD / task / "*/target/compiled/*/models/**/*.sql"), recursive=True):
        if Path(path).stem.lower() == model.lower():
            return Path(path).read_text()
    raise FileNotFoundError(f"{task}.{model}")


def sample_models(n: int, seed: int) -> list[tuple[str, str]]:
    """n data models from n different tasks (seeded)."""
    report = json.loads((REBUILD / "_compare_report.json").read_text())
    by_task: dict[str, list[str]] = {}
    for key in sorted(report):
        task, model = key.split(".", 1)
        by_task.setdefault(task, []).append(model)
    rng = random.Random(seed)
    tasks = sorted(by_task)
    rng.shuffle(tasks)
    return [(t, rng.choice(by_task[t])) for t in tasks[:n]]


class Grader:
    """One Snowflake session; grades a materialized table like eva_stage2."""

    def __init__(self) -> None:
        self.conn = get_connector("snowflake", json.loads(CREDENTIAL.read_text()))
        self.conn.query(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {STATEMENT_TIMEOUT_SEC}")

    def close(self) -> None:
        self.conn.close()

    def columns(self, fqn: str) -> list[tuple[str, str]]:
        catalog, schema, table = fqn.split(".")
        df = self.conn.query(
            f"SELECT column_name, data_type FROM {catalog}.information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = '{table}' ORDER BY ordinal_position")
        return [(str(r[0]).upper(), str(r[1])) for r in df.itertuples(index=False)]

    def materialize(self, task: str, model: str, sql: str) -> None:
        self.conn.query(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{task}")
        self.conn.query(f"CREATE OR REPLACE TABLE {DATABASE}.{task}.{model} AS\n{sql}")

    def _eval_query(self, task: str, model: str) -> str:
        path = EVAL / "sql" / task / f"{model}.sql"
        if path.exists():
            return self.conn.prepare_evaluation_sql(path.read_text(), DATABASE)
        return f"SELECT * FROM {DATABASE}.{task}.{model}"

    def grade(self, task: str, model: str, csv_path: Path, gt: pd.DataFrame) -> tuple[dict, pd.DataFrame | None]:
        query = self._eval_query(task, model)
        rows = int(self.conn.query(f"SELECT COUNT(*) FROM ({query.rstrip().rstrip(';')})").iloc[0, 0])
        if rows != len(gt):
            # check_corretness compares column vectors, which never match
            # when the lengths differ; skip fetching the table.
            return {"status": "ok", "match": False, "rows": rows, "reason": "row count"}, None
        df = self.conn.query(query)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=True)
        keys = table_keys(task, model)
        res = check_corretness(sort_by_keys(gt, keys), sort_by_keys(df, keys))
        res["rows"] = rows
        return res, df


def same_output(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Exact equality of two outputs (as written to CSV), ignoring row order;
    numbers may differ only by float noise (relative 1e-9)."""
    if a.shape != b.shape or [c.lower() for c in a.columns] != [c.lower() for c in b.columns]:
        return False
    cols = list(a.columns)
    b = b.set_axis(cols, axis=1)
    a = a.fillna("\0").sort_values(cols).reset_index(drop=True)
    b = b.fillna("\0").sort_values(cols).reset_index(drop=True)
    if a.equals(b):
        return True
    for c in cols:
        if a[c].equals(b[c]):
            continue
        x = pd.to_numeric(a[c].replace("\0", np.nan), errors="coerce")
        y = pd.to_numeric(b[c].replace("\0", np.nan), errors="coerce")
        if x.isna().sum() != (a[c] == "\0").sum() or y.isna().sum() != (b[c] == "\0").sum():
            return False
        if not np.allclose(x.to_numpy(float), y.to_numpy(float), rtol=1e-9, atol=0, equal_nan=True):
            return False
    return True


def run_model(task: str, model: str, args: argparse.Namespace) -> list[dict]:
    grader = Grader()
    out: list[dict] = []
    try:
        sql = compiled_sql(task, model)
        columns = {t: grader.columns(t) for t in mutate.referenced_tables(sql)}
        candidates = mutate.mutants(sql, columns, per_operator=args.per_operator, seed=args.seed)
        gt = pd.read_csv(GT_CSV / task / f"{model}.csv", dtype=str, keep_default_na=True)
        csv_dir = OUT / "csv" / task / model

        grader.materialize(task, model, sql)
        base_res, base_df = grader.grade(task, model, csv_dir / "original.csv", gt)
        base = {"task": task, "model": model, "id": "original", "operator": "original",
                "verifier_pass": bool(base_res.get("match")), "rows": base_res.get("rows")}
        log(base)
        out.append(base)
        if not base["verifier_pass"] or base_df is None:
            return out

        for i, m in enumerate(candidates):
            rec = {"task": task, "model": model, "id": f"m{i:02d}", "operator": m["operator"],
                   "description": m["description"], "sql": m["sql"]}
            started = time.time()
            try:
                grader.materialize(task, model, m["sql"])
                res, df = grader.grade(task, model, csv_dir / f"m{i:02d}.csv", gt)
                rec["verifier_pass"] = bool(res.get("match"))
                rec["rows"] = res.get("rows")
                rec["unmatched"] = res.get("unmatched")
                if df is not None and same_output(df, base_df):
                    rec["class"] = "equivalent"
                elif rec["verifier_pass"]:
                    rec["class"] = "survived"
                else:
                    rec["class"] = "killed"
            except Exception as e:
                rec["class"] = "invalid"
                rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            rec["seconds"] = round(time.time() - started, 1)
            log(rec)
            out.append(rec)
        return out
    finally:
        grader.close()


def log(rec: dict) -> None:
    with _lock:
        with open(OUT / "results.jsonl", "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        print(f"{rec['task']}.{rec['model']} {rec['id']:9s} {rec.get('class', 'pass' if rec.get('verifier_pass') else 'FAIL')}"
              f" {rec.get('operator')} {rec.get('description', '')[:90]}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sample", type=int, default=20)
    p.add_argument("--seed", type=int, default=20261014)
    p.add_argument("--per-operator", type=int, default=3)
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.jsonl").unlink(missing_ok=True)
    models = sample_models(args.sample, args.seed)
    (OUT / "sample.json").write_text(json.dumps(
        {"seed": args.seed, "per_operator": args.per_operator, "models": [f"{t}.{m}" for t, m in models]}, indent=2))
    print("sample:", ", ".join(f"{t}.{m}" for t, m in models), flush=True)

    setup = Grader()
    setup.conn.query(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
    setup.close()
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(lambda tm: run_model(tm[0], tm[1], args), models))


if __name__ == "__main__":
    main()
