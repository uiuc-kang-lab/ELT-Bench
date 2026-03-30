# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
## Column: AD_GROUP_NAME

**Description:**
The name of the corresponding ad group.

---

## Root Cause
**No semantic error: Values match 100%**

### Current SQL Logic
```sql
SELECT
    ...
    agh.ad_group_name,
    ...
FROM ad_performance ap
LEFT JOIN ad_group_history agh ON ap.ad_group_id = agh.ad_group_id
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100%.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Name of the ad group associated with the ad performance

* **What the SQL actually computes:**
  * Correctly joins to ad_group_history to get ad_group_name
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| AD_GROUP_NAME | Count |
| ------------- | ----- |
| 7Cmqte55GaD2sSkv932xhg== | 14 |
| NULL | 298 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Non-null count | 14 | 14 |
| Null count | 298 | 298 |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The AD_GROUP_NAME column is correctly implemented.
