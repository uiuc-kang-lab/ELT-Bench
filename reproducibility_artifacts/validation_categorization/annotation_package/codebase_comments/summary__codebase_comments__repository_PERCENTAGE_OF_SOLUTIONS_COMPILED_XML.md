# Column Mismatch Summary

## Database: codebase_comments
## Table: repository
## Column: PERCENTAGE_OF_SOLUTIONS_COMPILED_XML

**Description:**
The percentage of the methods' solutions that need to be compiled among the methods whose comments is XML format within the repository

---

## Root Cause
**Two issues: (1) WASCOMPILED value inversion - should use WASCOMPILED=0 for "need compiled", (2) Missing NULL handling - repos without XML methods should return NULL, not 0**

### Incorrect SQL Logic
```sql
method_solution_stats AS (
    SELECT
        s.REPOID AS repo_id,
        COUNT(CASE WHEN m.COMMENTISXML = 1 THEN 1 END) AS xml_methods_count,
        COUNT(CASE WHEN m.COMMENTISXML = 1 AND s.WASCOMPILED = 1 THEN 1 END) AS xml_methods_compiled_count
    FROM {{ source('airbyte_schema', 'METHOD') }} m
    JOIN {{ source('airbyte_schema', 'SOLUTION') }} s ON m.SOLUTIONID = s.ID
    GROUP BY s.REPOID
)
...
CASE
    WHEN mss.xml_methods_count > 0
    THEN (mss.xml_methods_compiled_count::FLOAT / mss.xml_methods_count::FLOAT) * 100
    ELSE 0
END AS percentage_of_solutions_compiled_XML
```

### Correct SQL Logic
```sql
method_solution_stats AS (
    SELECT
        s.REPOID AS repo_id,
        COUNT(CASE WHEN m.COMMENTISXML = 1 THEN 1 END) AS xml_methods_count,
        COUNT(CASE WHEN m.COMMENTISXML = 1 AND s.WASCOMPILED = 0 THEN 1 END) AS xml_methods_need_compiled_count
    FROM {{ source('airbyte_schema', 'METHOD') }} m
    JOIN {{ source('airbyte_schema', 'SOLUTION') }} s ON m.SOLUTIONID = s.ID
    GROUP BY s.REPOID
)
...
CASE
    WHEN mss.xml_methods_count > 0
    THEN (mss.xml_methods_need_compiled_count::FLOAT / mss.xml_methods_count::FLOAT) * 100
    ELSE NULL
END AS percentage_of_solutions_compiled_XML
```

---

## Why the Original Logic Is Wrong

* **Issue 1 - WASCOMPILED inversion:**
  * The SQL counts XML methods where `WASCOMPILED = 1` (already compiled)
  * The description asks for methods that "need to be compiled"
  * Solutions that "need to be compiled" have `WASCOMPILED = 0`

* **Issue 2 - NULL handling:**
  * The SQL returns 0 for repos without XML methods (`ELSE 0`)
  * The GT returns NULL for repos without XML methods
  * A percentage is undefined when there are no XML methods to calculate from

**Schema context:**
- `Method.CommentIsXml`: "whether the comment is XML format or not"
- `Solution.WasCompiled`: "whether this solution needs to be compiled or not"
  - Value 1 = was compiled (past tense)
  - Value 0 = was not compiled (needs compilation)

---

## Evidence

**Key comparison demonstrating the error:**

| Repo ID | XML Methods | WASCOMPILED=1 | WASCOMPILED=0 | Wrong (opt1) | Correct (opt2) | GT |
| ------- | ----------- | ------------- | ------------- | ------------ | -------------- | -- |
| 3       | 41          | 41            | 0             | 100.0        | 0.0            | 0.0 |
| 6       | 58          | 58            | 0             | 100.0        | 0.0            | 0.0 |
| 11      | 22          | 22            | 0             | 100.0        | 0.0            | 0.0 |
| 1       | 0 (none)    | -             | -             | 0.0          | NULL           | NULL |
| 2       | 0 (none)    | -             | -             | 0.0          | NULL           | NULL |

**GT value analysis:**
- Repos with XML methods: 43,973 (all have GT = 0.0)
- Repos without XML methods: 97,017 (all have GT = NULL)

**Impact:**
* Current implementation: **0/140,990 matches (0.0%)**
* Corrected implementation: **140,990/140,990 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
All XML method solutions in this dataset were already compiled (`WASCOMPILED=1`), so the percentage of methods that "need to be compiled" (`WASCOMPILED=0`) is 0% for all repos with XML methods. Repos without XML methods should return NULL since the percentage is undefined.
