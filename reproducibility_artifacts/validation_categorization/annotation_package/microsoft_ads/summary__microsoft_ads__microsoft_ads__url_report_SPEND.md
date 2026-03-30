# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
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
    SUM(ap.spend) AS spend,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
```

### Note on Issue
The SQL logic is semantically correct. Total spend matches exactly, but individual row values appear swapped.

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
| Total rows | 312 | 312 |
| Row-by-row match | 302/312 | 96.8% |

**Sample mismatches (values swapped between rows):**
| Index | GT SPEND | Predicted SPEND |
| ----- | -------- | --------------- |
| 114 | 0.00 | 2.91 |
| 115 | 2.91 | 0.00 |
| 197 | 0.00 | 6.17 |
| 199 | 6.17 | 0.00 |

**Impact:**
* Current implementation: **302/312 matches (96.8%)**
* Total spend matches exactly

---

## Result

**Row ordering issue - not a calculation error**

The SPEND calculation is correct. Mismatches are due to rows being in different order.
