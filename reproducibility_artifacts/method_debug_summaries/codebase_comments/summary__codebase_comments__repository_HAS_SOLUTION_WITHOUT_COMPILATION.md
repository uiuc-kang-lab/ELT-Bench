# Column Mismatch Summary

## Database: codebase_comments
## Table: repository
## Column: HAS_SOLUTION_WITHOUT_COMPILATION

**Description:**
Set to 1 if the repository has at least one solution that does not need to be compiled; otherwise, set to 0.

---

## Root Cause
**Semantic inversion: "does not need to be compiled" means WASCOMPILED=1 (was already compiled), not WASCOMPILED=0 (not compiled yet)**

### Incorrect SQL Logic
```sql
solution_stats AS (
    SELECT
        REPOID AS repo_id,
        ...
        MAX(CASE WHEN WASCOMPILED = 0 THEN 1 ELSE 0 END) AS has_solution_without_compilation
    FROM {{ source('airbyte_schema', 'SOLUTION') }}
    GROUP BY REPOID
)
```

### Correct SQL Logic
```sql
solution_stats AS (
    SELECT
        REPOID AS repo_id,
        ...
        MAX(CASE WHEN WASCOMPILED = 1 THEN 1 ELSE 0 END) AS has_solution_without_compilation
    FROM {{ source('airbyte_schema', 'SOLUTION') }}
    GROUP BY REPOID
)
```

---

## Why the Original Logic Is Wrong

* The column description asks for solutions that "do not need to be compiled"
* The SQL checks for `WASCOMPILED = 0`, interpreting it as "without compilation"
* However, `WASCOMPILED` indicates past status:
  * `WASCOMPILED = 1`: The solution **was compiled** (compilation already done - does NOT need further compilation)
  * `WASCOMPILED = 0`: The solution **was not compiled** (compilation still pending - NEEDS compilation)
* A solution that "does not need to be compiled" is one where compilation was already completed (`WASCOMPILED = 1`)

**Schema context from `Solution.csv`:**
- `WasCompiled`: "whether this solution needs to be compiled or not"
- The field uses past tense - indicating what already happened

---

## Evidence

**Key comparison demonstrating the error:**

| Repo ID | Any WASCOMPILED=0 | Any WASCOMPILED=1 | Wrong Logic | Correct Logic | GT |
| ------- | ----------------- | ----------------- | ----------- | ------------- | -- |
| 1       | No                | Yes               | 0           | 1             | 1  |
| 2       | No                | Yes               | 0           | 1             | 1  |
| 3       | No                | Yes               | 0           | 1             | 1  |
| 5       | Yes               | No                | 1           | 0             | 0  |
| 9       | Yes               | No                | 1           | 0             | 0  |

**Value distribution:**
- GT: 0=66,077, 1=74,913
- Predicted (wrong): 0=82,933, 1=58,057

**Impact:**
* Current implementation: **46,668/140,990 matches (33.1%)**
* Corrected implementation: **140,990/140,990 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The phrase "does not need to be compiled" refers to solutions where compilation is already complete (`WASCOMPILED = 1`). The SQL incorrectly interpreted this as solutions where `WASCOMPILED = 0`, which actually means compilation is still required. The `WasCompiled` field indicates the past state (was it compiled?), not the future requirement (does it need compilation?).

**Repositories with at least one solution that does not need compilation:**
- 74,913 repositories have at least one solution with `WASCOMPILED = 1` (already compiled, no further compilation needed)
