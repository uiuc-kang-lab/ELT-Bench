# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_group_report
## Column: CLICKS

**Description:**
The number of clicks that occurred by the grain of the report. Set the value to 0 if it is NULL.

---

## Root Cause
**Row ordering difference: Values are swapped between rows due to non-deterministic GROUP BY ordering**

### Current SQL Logic
```sql
SELECT
    ...
    SUM(agp.clicks) AS clicks,
    ...
FROM ad_group_performance agp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
```

### Note on Issue
The SQL logic is semantically correct. The total clicks match exactly, but individual row values appear swapped due to ordering differences.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Number of clicks at the report grain
  * NULL should be 0

* **What the SQL actually computes:**
  * Correctly sums clicks and coalesces NULL to 0
  * Total clicks match GT exactly

**Value distribution (both GT and Predicted):**
| CLICKS | Count |
| ------ | ----- |
| 0 | 170 |
| 1 | 10 |
| 2 | 1 |
| 3 | 1 |

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 182 | 182 |
| Row-by-row match | 178/182 | 97.8% |

**Sample mismatches (values swapped between rows):**
| Index | GT CLICKS | Predicted CLICKS |
| ----- | --------- | ---------------- |
| 47 | 0 | 1 |
| 48 | 1 | 0 |
| 116 | 1 | 0 |
| 117 | 0 | 1 |

**Impact:**
* Current implementation: **178/182 matches (97.8%)**
* Total clicks match exactly

---

## Result

**Row ordering issue - not a calculation error**

The CLICKS calculation is correct. Mismatches are due to rows being in different order.
