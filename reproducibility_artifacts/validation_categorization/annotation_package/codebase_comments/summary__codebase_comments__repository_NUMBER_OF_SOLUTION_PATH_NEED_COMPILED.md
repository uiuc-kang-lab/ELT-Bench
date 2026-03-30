# Column Mismatch Summary

## Database: codebase_comments
## Table: repository
## Column: NUMBER_OF_SOLUTION_PATH_NEED_COMPILED

**Description:**
Number of solution paths that need to be compiled if the user wants to implement the repository, replace NULL values with 0.

---

## Root Cause
**Semantic inversion: WASCOMPILED=1 means the solution WAS compiled (already done), WASCOMPILED=0 means it NEEDS to be compiled (still required)**

### Incorrect SQL Logic
```sql
solution_stats AS (
    SELECT
        REPOID AS repo_id,
        COUNT(CASE WHEN WASCOMPILED = 1 THEN 1 END) AS number_of_solution_path_need_compiled,
        ...
    FROM {{ source('airbyte_schema', 'SOLUTION') }}
    GROUP BY REPOID
)
```

### Correct SQL Logic
```sql
solution_stats AS (
    SELECT
        REPOID AS repo_id,
        COUNT(CASE WHEN WASCOMPILED = 0 THEN 1 END) AS number_of_solution_path_need_compiled,
        ...
    FROM {{ source('airbyte_schema', 'SOLUTION') }}
    GROUP BY REPOID
)
```

---

## Why the Original Logic Is Wrong

* The `WasCompiled` column in the Solution table indicates the compilation status:
  * `WASCOMPILED = 1`: The solution **was** already compiled (compilation completed)
  * `WASCOMPILED = 0`: The solution was **not** compiled (compilation still needed)
* The column description asks for "solution paths that **need** to be compiled"
* The SQL incorrectly counts solutions where `WASCOMPILED = 1` (already compiled)
* The correct logic counts solutions where `WASCOMPILED = 0` (need compilation)

**Schema context from `Solution.csv`:**
- `WasCompiled`: "whether this solution needs to be compiled or not"
- Value 1 = was compiled (past tense, already done)
- Value 0 = was not compiled (needs to be compiled)

---

## Evidence

**Key comparison demonstrating the error:**

| Repo ID | Wrong Logic (WASCOMPILED=1) | Correct Logic (WASCOMPILED=0) | Ground Truth |
| ------- | --------------------------- | ----------------------------- | ------------ |
| 1       | 1                           | 0                             | 0            |
| 2       | 1                           | 0                             | 0            |
| 5       | 0                           | 2                             | 2            |
| 9       | 0                           | 12                            | 12           |

**Solution data distribution:**
- Total solutions: 338,087
- WASCOMPILED=0 (needs compilation): 178,493 (52.8%)
- WASCOMPILED=1 (was compiled): 159,594 (47.2%)

**Impact:**
* Current implementation: **42,678/140,990 matches (30.3%)**
* Corrected implementation: **140,990/140,990 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The `WasCompiled` flag uses past tense - it indicates whether compilation already happened (1) or not (0). Solutions that "need to be compiled" are those where `WASCOMPILED = 0`, meaning compilation has not yet occurred.
