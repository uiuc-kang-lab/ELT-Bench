# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_group_report
## Column: DEVICE_TYPE

**Description:**
The device type associated with this record; values include but may not be limited to 'Computer', 'Smartphone', 'Tablet' and 'Unknown'.

---

## Root Cause
**Row ordering difference: Values are correct but appear in different row positions due to GROUP BY/ORDER BY differences**

### Current SQL Logic
```sql
SELECT
    ...
    agp.device_type,
    ...
FROM ad_group_performance agp
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100% when compared row-by-row.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Device type of the user who saw/clicked the ad
  * Values: 'Computer', 'Smartphone', 'Tablet', 'Unknown'

* **What the SQL actually computes:**
  * Correctly passes through the device_type from source
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| DEVICE_TYPE | Count |
| ----------- | ----- |
| Computer | 161 |
| Smartphone | 21 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 182 | 182 |
| Computer count | 161 | 161 |
| Smartphone count | 21 | 21 |

**Impact:**
* Current implementation: **182/182 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The DEVICE_TYPE column is correctly implemented.
