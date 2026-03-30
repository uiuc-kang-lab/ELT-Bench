# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__campaign_report
## Column: ALL_CONVERSIONS_VALUE

**Description:**
The revenue reported by the advertiser as a result of the all_conversions figure. This will include revenue from conversions regardless of the value of the conversion goal's ExcludeFromBidding property in Microsoft Ads. Set the value to 0 if it is NULL.

---

## Root Cause
**Row ordering mismatch: Values appear swapped between rows due to GROUP BY aggregation differences**

### Incorrect SQL Logic
```sql
SELECT
    ...
    SUM(cp.all_conversions_value) AS all_conversions_value,
    ...
FROM campaign_performance cp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
```

### Note on Issue
The SQL logic is semantically correct, but the aggregation groups data differently than the ground truth, resulting in values appearing on different rows.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Revenue from all conversions, regardless of ExcludeFromBidding setting
  * Set to 0 if NULL

* **What the SQL actually computes:**
  * The calculation is correct
  * The mismatch is due to row ordering/grouping differences
  * Values of 0.02 and 0.00 are swapped between rows 1461 and 1465

---

## Evidence

**Key comparison demonstrating the error:**

| Index | GT ALL_CONVERSIONS_VALUE | Predicted ALL_CONVERSIONS_VALUE |
| ----- | ------------------------ | ------------------------------- |
| 1461 | 0.02 | 0.00 |
| 1465 | 0.00 | 0.02 |

**Impact:**
* Current implementation: **1518/1520 matches (99.9%)**
* The 2 mismatches are due to row ordering, not calculation errors

---

## Result

**Near-perfect match with potential ordering issue**

The calculation logic is correct but rows may be assigned to different groups. This could be due to:
1. Different sort order in GROUP BY
2. Ties in grouping columns being resolved differently
3. Non-deterministic ordering when multiple rows have same key values
