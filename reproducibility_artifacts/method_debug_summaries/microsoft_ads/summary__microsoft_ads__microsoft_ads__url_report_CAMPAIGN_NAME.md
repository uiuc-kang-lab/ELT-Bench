# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
## Column: CAMPAIGN_NAME

**Description:**
The name of the campaign.

---

## Root Cause
**No semantic error: Values match 100%**

### Current SQL Logic
```sql
SELECT
    ...
    ch.campaign_name,
    ...
FROM ad_performance ap
LEFT JOIN campaign_history ch ON ap.campaign_id = ch.campaign_id
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100%.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Name of the campaign associated with the ad performance

* **What the SQL actually computes:**
  * Correctly joins to campaign_history to get campaign_name
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| CAMPAIGN_NAME | Count |
| ------------- | ----- |
| PafijluKrvfPOb+f94eCDw== | 55 |
| NULL | 257 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Non-null count | 55 | 55 |
| Null count | 257 | 257 |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The CAMPAIGN_NAME column is correctly implemented.
