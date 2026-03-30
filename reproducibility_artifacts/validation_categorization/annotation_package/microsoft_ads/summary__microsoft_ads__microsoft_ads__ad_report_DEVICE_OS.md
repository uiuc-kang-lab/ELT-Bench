# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
## Column: DEVICE_OS

**Description:**
The device operating system associated with this record; values include but may not be limited to 'Windows', 'iOS', 'Android', 'Other', 'BlackBerry' and 'Unknown'.

---

## Root Cause
**Row ordering difference: Values are correct but appear in different row positions due to GROUP BY/ORDER BY differences**

### Current SQL Logic
```sql
SELECT
    ...
    ap.device_os,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100% when compared row-by-row in the original order, but rows may appear in different positions when sorted differently.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Device OS of the user who saw/clicked the ad
  * Values: 'Windows', 'iOS', 'Android', 'Other', 'BlackBerry', 'Unknown'

* **What the SQL actually computes:**
  * Correctly passes through the device_os from source
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| DEVICE_OS | Count |
| --------- | ----- |
| Windows | 246 |
| Unknown | 28 |
| Android | 25 |
| iOS | 13 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Windows count | 246 | 246 |
| Unknown count | 28 | 28 |
| Android count | 25 | 25 |
| iOS count | 13 | 13 |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The DEVICE_OS column is correctly implemented. Both GT and predicted have identical value distributions.
