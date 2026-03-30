# Column Mismatch Summary

## Database: linkedin
## Table: linkedin_ads__campaign_group_report
## Column: IMPRESSIONS

### Description
See table-level summary

---

## Root Cause
**Missing ORDER BY clause causes row ordering mismatch - values are correct but in different positions**

### Incorrect SQL Logic
```sql
SELECT
    DATE(DAY) as date_day,
    campaign_group_id,
    SUM(impressions) as impressions,
    ...
FROM campaign_analytics
GROUP BY date_day, campaign_group_id
-- No ORDER BY clause
```

### Correct SQL Logic
```sql
SELECT
    DATE(DAY) as date_day,
    CAST(campaign_group_id AS INTEGER) as campaign_group_id,
    SUM(impressions) as impressions,
    ...
FROM campaign_analytics
GROUP BY DATE(DAY), campaign_group_id
ORDER BY date_day, campaign_group_id
```

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Min IMPRESSIONS | same | same |
| Max IMPRESSIONS | same | same |
| Total Sum | same | same |
| Row Order | sorted by date | unsorted |

**Verification:**
* Row count matches (20 rows each)
* All dates present in both datasets
* Numeric totals match when aggregated

**Impact:**
* Current implementation: **0/20 matches (0%)** due to row ordering
* Corrected implementation with ORDER BY: **20/20 matches (100%)**

---

## Result
**Key insight:**
The IMPRESSIONS values are calculated correctly. The mismatch is purely a row ordering issue. Adding `ORDER BY date_day, campaign_group_id` will align the rows correctly and achieve 100% match.
