# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
## Column: IMPRESSIONS

**Description:**
The number of impressions that occurred by the grain of the report. Set the value to 0 if it is NULL.

---

## Root Cause
**Row ordering difference: Values are swapped between rows due to non-deterministic GROUP BY ordering**

### Current SQL Logic
```sql
SELECT
    ...
    SUM(ap.impressions) AS impressions,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
```

### Note on Issue
The SQL logic is semantically correct. The total impressions match exactly, but individual row values appear swapped due to ordering differences.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Number of ad impressions at the report grain
  * NULL should be 0

* **What the SQL actually computes:**
  * Correctly sums impressions and coalesces NULL to 0
  * Total impressions match GT exactly
  * Row-level mismatches are due to ordering, not calculation

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Row-by-row match | 272/312 | 87.2% |

**Sample mismatches (values swapped between rows):**
| Index | GT IMPRESSIONS | Predicted IMPRESSIONS |
| ----- | -------------- | --------------------- |
| 4 | 1 | 2 |
| 5 | 2 | 1 |
| 28 | 1 | 8 |
| 29 | 8 | 1 |

**Impact:**
* Current implementation: **272/312 matches (87.2%)**
* Total impressions match exactly

---

## Result

**Row ordering issue - not a calculation error**

The IMPRESSIONS calculation is correct. Mismatches are due to rows being in different order when there are ties in the GROUP BY columns.
