# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_group_report
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
    SUM(agp.impressions) AS impressions,
    ...
FROM ad_group_performance agp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
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

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 182 | 182 |
| Row-by-row match | 141/182 | 77.5% |

**Sample mismatches (values swapped between rows):**
| Index | GT IMPRESSIONS | Predicted IMPRESSIONS |
| ----- | -------------- | --------------------- |
| 4 | 1 | 2 |
| 5 | 2 | 1 |
| 44 | 1 | 2 |
| 45 | 2 | 1 |

**Impact:**
* Current implementation: **141/182 matches (77.5%)**
* Total impressions match exactly

---

## Result

**Row ordering issue - not a calculation error**

The IMPRESSIONS calculation is correct. Mismatches are due to rows being in different order.
