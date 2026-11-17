# Mutation operators

[mutate.py](mutate.py) generates the mutants used to test the Stage 2
verifier. Each operator changes one place in a ground-truth query (parsed with
sqlglot in the Snowflake dialect). The ground-truth SQL is not included in
this repository.

| Operator | Change | Mistake it models |
|---|---|---|
| `drop_filter` | Remove one WHERE/HAVING condition, or the whole clause | A missing filter |
| `join_type` | INNER JOIN ↔ LEFT JOIN | The wrong join type |
| `join_key` | Replace a join-key column with another column of the same table and type family | Joining on the wrong column |
| `aggregate` | SUM ↔ AVG, MIN ↔ MAX, COUNT(x) ↔ COUNT(DISTINCT x) | The wrong aggregate |
| `boundary` | `>` ↔ `>=`, `<` ↔ `<=` | An off-by-one boundary |
| `distinct` | Drop SELECT DISTINCT | Duplicate rows |
| `null_handling` | COALESCE/IFNULL/NVL(a, b, ...) → a | Missing NULL defaults |
| `tie_break` | In a window ORDER BY, flip the first key or drop the last key | Wrong ordering or tie-breaking |
| `scale` | `x * 100` → `x`; `ROUND(x, n)` → `x` | A fraction instead of a percentage; missing rounding |
