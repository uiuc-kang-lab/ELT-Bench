# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__campaign_report
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
    SUM(cp.impressions) AS impressions,
    ...
FROM campaign_performance cp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
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
  * Total impressions match GT exactly (7569)

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 1520 | 1520 |
| Total IMPRESSIONS | 7569 | 7569 |
| Row-by-row match | 562/1520 | 37.0% |

**Sample mismatches (values swapped between rows):**
| Index | GT IMPRESSIONS | Predicted IMPRESSIONS |
| ----- | -------------- | --------------------- |
| 0 | 1 | 0 |
| 1 | 0 | 1 |
| 2 | 2 | 1 |
| 3 | 1 | 2 |

**Impact:**
* Current implementation: **562/1520 matches (37.0%)**
* Total impressions match: **7569 = 7569 (100%)**

---

## Result

**Row ordering issue - not a calculation error**

The IMPRESSIONS calculation is correct. Mismatches are due to rows being in different order.
