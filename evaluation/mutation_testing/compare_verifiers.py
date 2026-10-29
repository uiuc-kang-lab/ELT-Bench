"""Grade the stage-2 mutation-testing outputs (agent_results/_mutation) with three verifiers and compare.

  old          the comparator of the original ELT-Bench (branch origin/eltbench_old, commit 20cb046,
               evaluation/eva_stage2.py; copied verbatim below): files read with pd.read_csv defaults,
               columns matched by exact name, element-wise compare with a 1% band for Python int/float
               pairs and exact equality otherwise. Rows are first sorted by sort_key.json, so only the
               comparator differs. "old, unsorted" keeps the old row-by-row alignment as well.
  rtol         eva_stage2.check_corretness(rule="rtol"): 1% relative tolerance (the verifier until 2026-10-19)
  typed        eva_stage2.check_corretness(rule="typed"): the type-aware default since 2026-10-19

All use the current GT (ground_truth/gt_snowflake) and the same mutant outputs. Mutants rejected by the row
count have no CSV; every verifier rejects them (vectors of different length never match).

    python compare_verifiers.py   -> agent_results/_mutation_verifiers/{verdicts.jsonl,summary.json}
"""
from __future__ import annotations

import collections
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
sys.path.insert(0, str(EVAL))
os.chdir(EVAL)
from eva_stage2 import check_corretness, sort_by_keys, table_keys  # noqa: E402
from mutate import OPERATORS  # noqa: E402

GT = EVAL.parent / "ground_truth/gt_snowflake"
MUT = EVAL / "agent_results/_mutation"
OUT = EVAL / "agent_results/_mutation_verifiers"
VERIFIERS = ["old", "old, unsorted", "rtol", "typed"]


def old_check_corretness(df_gt, df):
    """origin/eltbench_old:evaluation/eva_stage2.py check_corretness, returning instead of logging."""
    matched_cols = []
    unmatched_cols = []
    missed_cols = []

    def vectors_match(v1, v2, tol=1e-2):
        if len(v1) != len(v2):
            return False
        count = 0
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if float(b) > float(a) * 1.01 or float(b) < float(a) * 0.99:
                    return False
            elif a != b:
                return False
            count += 1
        return True

    tolerance = 1e-7

    for gold_col in df_gt.columns:
        if gold_col in df.columns:
            if not vectors_match(df_gt[gold_col], df[gold_col], tolerance):
                unmatched_cols.append(gold_col)
            else:
                matched_cols.append(gold_col)
        else:
            missed_cols.append(gold_col)
    return {"match": not unmatched_cols and not missed_cols, "unmatched": unmatched_cols, "missed": missed_cols}


def grade_model(task: str, model: str, ids: list[str]) -> list[dict]:
    keys = table_keys(task, model)
    gt_old = pd.read_csv(GT / task / f"{model}.csv")  # old reader: pandas type inference
    gt_old_sorted = sort_by_keys(gt_old, keys)
    gt_str = sort_by_keys(pd.read_csv(GT / task / f"{model}.csv", dtype=str, keep_default_na=True), keys)
    out = []
    for i in ids:
        p = MUT / "csv" / task / model / f"{i}.csv"
        rec = {"task": task, "model": model, "id": i}
        df_old = pd.read_csv(p)
        r = old_check_corretness(gt_old_sorted, sort_by_keys(df_old, keys))
        rec["old"], rec["old_unmatched"], rec["old_missed"] = r["match"], r["unmatched"], r["missed"]
        rec["old, unsorted"] = old_check_corretness(gt_old, df_old)["match"]
        df = sort_by_keys(pd.read_csv(p, dtype=str, keep_default_na=True), keys)
        for rule in ("rtol", "typed"):
            r = check_corretness(gt_str, df, rule)
            rec[rule], rec[f"{rule}_unmatched"] = r["match"], r["unmatched"]
        out.append(rec)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = [json.loads(l) for l in open(MUT / "results.jsonl")]
    todo = collections.defaultdict(list)
    for m in log:
        if m.get("class") == "invalid" or (m.get("class") == "killed" and m.get("unmatched") is None):
            continue  # invalid, or rejected by the row count (no CSV; a leftover file may exist)
        todo[(m["task"], m["model"])].append(m["id"])
    with ProcessPoolExecutor(32) as pool:
        futs = [pool.submit(grade_model, t, m, ids) for (t, m), ids in todo.items()]
        graded = {(r["task"], r["model"], r["id"]): r for f in futs for r in f.result()}
    with open(OUT / "verdicts.jsonl", "w") as f:
        for r in graded.values():
            f.write(json.dumps(r) + "\n")

    table = {v: collections.defaultdict(collections.Counter) for v in VERIFIERS}
    survivors = {v: [] for v in VERIFIERS}
    false_rejections = {v: [] for v in VERIFIERS}
    for m in log:
        cls = m.get("class", "original")
        if cls == "invalid":
            continue
        r = graded.get((m["task"], m["model"], m["id"]))
        for v in VERIFIERS:
            passed = bool(r and r[v])
            op = m["operator"]
            if cls in ("original", "equivalent"):
                table[v][op][f"{cls} accepted"] += passed
                table[v][op][cls] += 1
                if not passed:
                    false_rejections[v].append(f"{m['task']}.{m['model']} {m['id']} {r.get(v.split(',')[0] + '_unmatched') if r else ''}")
            else:
                table[v][op]["killed" if not passed else "survived"] += 1
                if passed:
                    survivors[v].append(f"{m['task']}.{m['model']} {m['id']} [{op}] {m['description'][:70]}")
    summary = {}
    for v in VERIFIERS:
        tot = collections.Counter()
        for c in table[v].values():
            tot.update(c)
        catch = tot["killed"] / (tot["killed"] + tot["survived"])
        summary[v] = {"total": dict(tot), "catch_rate": round(catch, 4),
                      "per_operator": {op: dict(table[v][op]) for op in OPERATORS if op in table[v]},
                      "survivors": survivors[v], "false_rejections": false_rejections[v]}
        print(f"{v:14s} killed {tot['killed']:3d} survived {tot['survived']:3d} catch {catch:7.2%} | originals accepted "
              f"{tot['original accepted']}/{tot['original']} | equivalent accepted {tot['equivalent accepted']}/{tot['equivalent']}")
    print()
    for op in OPERATORS:
        print(f"{op:14s} " + "  ".join(f"{v}: {table[v][op]['killed']}/{table[v][op]['killed'] + table[v][op]['survived']}"
                                       for v in VERIFIERS))
    json.dump(summary, open(OUT / "summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
