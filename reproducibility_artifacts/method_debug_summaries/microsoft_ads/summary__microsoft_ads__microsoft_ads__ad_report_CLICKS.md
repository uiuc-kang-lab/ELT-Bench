# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
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
    SUM(ap.clicks) AS clicks,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
```

### Note on Issue
The SQL logic is semantically correct. The total clicks match exactly, but individual row values appear swapped due to ordering differences.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Number of clicks at the report grain (date, ad, device_os, device_type, network)
  * NULL should be 0

* **What the SQL actually computes:**
  * Correctly sums clicks and coalesces NULL to 0
  * Total clicks match GT exactly
  * Row-level mismatches are due to ordering, not calculation

**Value distribution (both GT and Predicted):**
| CLICKS | Count |
| ------ | ----- |
| 0 | 288 |
| 1 | 20 |
| 2 | 4 |

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Total CLICKS | 28 | 28 |
| Row-by-row match | 306/312 | 98.1% |

**Sample mismatches (values swapped between adjacent rows):**
| Index | GT CLICKS | Predicted CLICKS |
| ----- | --------- | ---------------- |
| 28 | 0 | 1 |
| 29 | 1 | 0 |
| 38 | 0 | 1 |
| 39 | 1 | 0 |

**Impact:**
* Current implementation: **306/312 matches (98.1%)**
* Total clicks match: **28 = 28 (100%)**

---

## Result

**Row ordering issue - not a calculation error**

The CLICKS calculation is correct. Mismatches are due to rows being in different order when there are ties in the GROUP BY columns.
