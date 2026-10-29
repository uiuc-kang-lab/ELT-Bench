"""Summarize agent_results/_mutation/results.jsonl (see run.py).

  catch rate          killed / (killed + survived): how often the verifier
                      rejects a mutant whose output differs from the original
  indistinguishable   equivalent / valid: mutants whose output equals the
                      original's, so no output-based grader can reject them
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from mutate import OPERATORS

OUT = Path(__file__).resolve().parent.parent / "agent_results/_mutation"


def main() -> None:
    rows = [json.loads(line) for line in open(OUT / "results.jsonl")]
    originals = [r for r in rows if r["id"] == "original"]
    mutants = [r for r in rows if r["id"] != "original"]
    print(f"models: {len(originals)} (original query passes the verifier: "
          f"{sum(r['verifier_pass'] for r in originals)})")

    table = collections.defaultdict(collections.Counter)
    for r in mutants:
        table[r["operator"]][r["class"]] += 1
        table["all"][r["class"]] += 1

    print(f"\n{'operator':14s} {'mutants':>7s} {'invalid':>7s} {'valid':>6s} {'equiv':>6s} "
          f"{'killed':>6s} {'surv':>5s} {'catch':>7s} {'indist':>7s}")
    for op in [*OPERATORS, "all"]:
        c = table.get(op)
        if not c:
            continue
        valid = c["equivalent"] + c["killed"] + c["survived"]
        differ = c["killed"] + c["survived"]
        catch = f"{c['killed'] / differ:.1%}" if differ else "-"
        indist = f"{c['equivalent'] / valid:.1%}" if valid else "-"
        print(f"{op:14s} {sum(c.values()):7d} {c['invalid']:7d} {valid:6d} {c['equivalent']:6d} "
              f"{c['killed']:6d} {c['survived']:5d} {catch:>7s} {indist:>7s}")

    for cls in ("survived", "equivalent"):
        print(f"\n{cls}:")
        for r in mutants:
            if r["class"] == cls:
                print(f"  {r['task']}.{r['model']} {r['id']} [{r['operator']}] {r['description'][:110]}")

    summary = {op: dict(c) for op, c in table.items()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
