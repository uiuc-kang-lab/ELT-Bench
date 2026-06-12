# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_group_report
## Column: SPEND

**Description:**
The amount of spend that occurred by the grain of the report. Set the value to 0 if it is NULL.

---

## Root Cause
**Row ordering difference: Values are swapped between rows due to non-deterministic GROUP BY ordering**

### Current SQL Logic
```sql
SELECT
    ...
    SUM(agp.spend) AS spend,
    ...
FROM ad_group_performance agp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
```

### Note on Issue
The SQL logic is semantically correct. The total spend matches exactly, but individual row values appear swapped due to ordering differences.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Amount spent on ads at the report grain
  * NULL should be 0

* **What the SQL actually computes:**
  * Correctly sums spend and coalesces NULL to 0
  * Total spend matches GT exactly

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 182 | 182 |
| Row-by-row match | 178/182 | 97.8% |

**Sample mismatches (values swapped between rows):**
| Index | GT SPEND | Predicted SPEND |
| ----- | -------- | --------------- |
| 47 | 0.00 | 6.95 |
| 48 | 6.95 | 0.00 |
| 116 | 8.82 | 0.00 |
| 117 | 0.00 | 8.82 |

**Impact:**
* Current implementation: **178/182 matches (97.8%)**
* Total spend matches exactly

---

## Result

**Row ordering issue - not a calculation error**

The SPEND calculation is correct. Mismatches are due to rows being in different order.
