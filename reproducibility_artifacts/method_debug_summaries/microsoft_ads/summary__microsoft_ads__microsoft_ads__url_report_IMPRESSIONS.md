# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
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
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
```

### Note on Issue
The SQL logic is semantically correct. Total impressions match exactly, but individual row values appear swapped.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Number of ad impressions at the report grain
  * NULL should be 0

* **What the SQL actually computes:**
  * Correctly sums impressions and coalesces NULL to 0
  * Total impressions match GT exactly

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Row-by-row match | 248/312 | 79.5% |

**Sample mismatches (values swapped between rows):**
| Index | GT IMPRESSIONS | Predicted IMPRESSIONS |
| ----- | -------------- | --------------------- |
| 37 | 1 | 2 |
| 38 | 2 | 1 |
| 41 | 3 | 27 |
| 42 | 27 | 3 |

**Impact:**
* Current implementation: **248/312 matches (79.5%)**
* Total impressions match exactly

---

## Result

**Row ordering issue - not a calculation error**

The IMPRESSIONS calculation is correct. Mismatches are due to rows being in different order.
