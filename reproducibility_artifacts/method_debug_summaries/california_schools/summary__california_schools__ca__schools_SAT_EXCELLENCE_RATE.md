# Column Mismatch Summary

## Database: california_schools
## Table: ca__schools
## Column: SAT_EXCELLENCE_RATE

### Description
The excellence rate of the SAT scores of the school

---

## Root Cause
**Three issues: (1) Returns percentage instead of ratio, (2) Returns 0 instead of NULL for missing data, (3) Missing record type filter**

### Incorrect SQL Logic
```sql
satscores AS (
    SELECT
        cds,
        NumTstTakr,
        NumGE1500
    FROM {{ source('airbyte_schema', 'satscores') }}
)

SELECT
    ...
    CASE
        WHEN sat.NumTstTakr > 0 THEN
            ROUND((sat.NumGE1500 / sat.NumTstTakr) * 100, 2)
        ELSE 0
    END AS SAT_excellence_rate
FROM schools s
LEFT JOIN satscores sat ON s.CDSCode = sat.cds
```

### Correct SQL Logic
```sql
satscores AS (
    SELECT
        cds,
        NumTstTakr,
        NumGE1500
    FROM {{ source('airbyte_schema', 'satscores') }}
    WHERE rtype = 'S'  -- Filter to School-level records only
)

SELECT
    ...
    CASE
        WHEN sat.cds IS NOT NULL AND sat.NumTstTakr > 0 THEN
            sat.NumGE1500 / sat.NumTstTakr  -- Return ratio, not percentage
        ELSE NULL  -- Return NULL for missing data, not 0
    END AS SAT_excellence_rate
FROM schools s
LEFT JOIN satscores sat ON s.CDSCode = sat.cds
```

---

## Why the Original Logic Is Wrong

1. **Percentage vs Ratio:**
   * The SQL multiplies by 100 to create a percentage (e.g., 52.94%)
   * The ground truth expects a ratio (e.g., 0.5294)
   * "Excellence rate" as a "rate" typically means a ratio (0-1), not a percentage (0-100)

2. **NULL vs 0 for Missing Data:**
   * The SQL returns 0 for schools without SAT data or with zero test takers
   * The ground truth returns NULL for these cases
   * This affects 15,417 schools without SAT data + 218 with SAT records but no test takers

3. **Missing Record Type Filter:**
   * The satscores table contains both School ('S') and District ('D') level records
   * Only school-level records (rtype = 'S') should be joined to schools
   * Without this filter, some schools incorrectly get NULL when they should have data

---

## Evidence

**Key comparison demonstrating the error:**

| School CDSCode    | NumGE1500 | NumTstTakr | Wrong Logic | Correct Logic | Ground Truth |
| ----------------- | --------- | ---------- | ----------- | ------------- | ------------ |
| 1100170109835     | 9         | 17         | 52.94       | 0.5294        | 0.5294       |
| 1100170112607     | 5         | 71         | 7.04        | 0.0704        | 0.0704       |
| 1611190000000     | 29        | 36         | 80.56       | 0.8056        | 0.8056       |
| 1611190000000     | 229       | 325        | 70.46       | 0.7046        | 0.7046       |

**NULL handling:**
| Scenario                        | Count   | Wrong Logic | Correct Logic | Ground Truth |
| ------------------------------- | ------- | ----------- | ------------- | ------------ |
| No SAT record                   | 15,417  | 0           | NULL          | NULL         |
| SAT record, NumTstTakr=0/NULL   | 218     | 0           | NULL          | NULL         |

**Record type distribution:**
```
rtype values in satscores:
S (School):   1,749 records
D (District): 520 records
```

**Impact:**
* Current implementation: **395/17,686 matches (2.2%)**
* Corrected implementation (with rtype='S' filter): **17,655/17,686 matches (99.8%)**

---

## Result
**Near-perfect match with corrected logic (99.8%)**

**31 remaining edge cases:**
These are schools where ground truth has a SAT_EXCELLENCE_RATE value but no matching school-level record exists in satscores. These may be schools whose SAT data was aggregated differently or from an alternate source.

**Key insights:**
1. "Rate" in "excellence rate" means a ratio (0-1), not a percentage (0-100)
2. Schools without SAT data should return NULL, not 0
3. The satscores table contains multiple record types; only 'S' (School) records should be used for school-level joins
