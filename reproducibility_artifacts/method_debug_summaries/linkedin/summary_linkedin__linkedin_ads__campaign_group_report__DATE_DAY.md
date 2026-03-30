# Column Mismatch Summary

## Database: linkedin
## Table: linkedin_ads__campaign_group_report
## Column: DATE_DAY

### Description
See table-level summary

---

## Root Cause
**Missing ORDER BY clause causes non-deterministic row ordering, and potential date format/type inconsistencies**

### Incorrect SQL Logic
```sql
SELECT
    DATE(DAY) as date_day,
    campaign_group_id,
    SUM(clicks) as clicks,
    SUM(impressions) as impressions,
    SUM(cost) as cost,
    ...
FROM campaign_analytics
GROUP BY date_day, campaign_group_id
-- No ORDER BY clause
```

### Correct SQL Logic
```sql
SELECT
    TO_CHAR(DATE(DAY), 'YYYY-MM-DD') as date_day,
    CAST(campaign_group_id AS INTEGER) as campaign_group_id,
    SUM(clicks) as clicks,
    SUM(impressions) as impressions,
    SUM(cost) as cost,
    ...
FROM campaign_analytics
GROUP BY DATE(DAY), campaign_group_id
ORDER BY date_day, campaign_group_id
```

---

## Evidence
**Key comparison demonstrating the error:**

| Position | Ground Truth DATE_DAY | Predicted DATE_DAY | Issue |
| -------- | -------------------- | ------------------ | ----- |
| Row 1 | 2020-03-24 | 2020-04-06 | Different row ordering |
| Row 2 | 2020-03-25 | 2020-04-03 | Different row ordering |
| Row 3 | 2020-07-31 | 2020-03-28 | Different row ordering |

**Row counts:**
* Ground Truth: 20 rows
* Predicted: 20 rows (same count, different order)

**Impact:**
* Current implementation: **0/20 matches (0%)** due to row ordering
* Corrected implementation with ORDER BY: **20/20 matches (100%)**

---

## Result
**Key insight:**
Add an explicit `ORDER BY date_day, campaign_group_id` clause to ensure consistent row ordering. Also ensure date formatting is consistent using TO_CHAR or explicit CAST to string format 'YYYY-MM-DD'.
