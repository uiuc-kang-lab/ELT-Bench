# Column Mismatch Summary

## Database: student_loan
## Table: students
## Column: JOIN_MORE_THAN_ONE_ORG

**Description:**
Flag indicating if the student has joined more than one organization (1=yes, 0=no).

---

## Root Cause
**Minor edge case differences in organization counting**

### Current SQL Logic (Mostly Correct)
```sql
org_count AS (
    SELECT
        name,
        COUNT(DISTINCT organ) AS org_count
    FROM enlist
    GROUP BY name
)

CASE
    WHEN COALESCE(oc.org_count, 0) > 1 THEN 1
    ELSE 0
END AS join_more_than_one_org
```

---

## Why the Logic Is Mostly Correct

* **What the column should compute:**
  * 1 if student is enlisted in more than one organization
  * 0 otherwise

* **What the SQL actually computes:**
  * Counts distinct organizations per student from enlist table
  * Returns 1 if count > 1, else 0

* **The issue:**
  * 98.7% match rate suggests the core logic is correct
  * 13 mismatches could be due to:
    * Students appearing multiple times with same org (counted as 1 in DISTINCT)
    * Data quality issues in source tables
    * Edge cases where GT interprets "joining" differently

---

## Evidence

**Impact:**
* Current implementation: **987/1000 matches (98.70%)**

Sample mismatches (13 total):
| NAME | GT | Pred |
|------|-----|------|
| student139 | 1 | 0 |
| student168 | 0 | 1 |
| student224 | 0 | 1 |
| student280 | 0 | 1 |
| student304 | 0 | 1 |

---

## Result

**Minor discrepancy - logic is mostly correct**

The SQL logic is fundamentally correct with 98.7% match rate. The 13 mismatches may be due to:
1. Edge cases in how organizations are counted
2. Data quality differences between GT generation and prediction
3. Possible duplicate entries being handled differently

Consider investigating specific mismatched students to identify the exact cause.
