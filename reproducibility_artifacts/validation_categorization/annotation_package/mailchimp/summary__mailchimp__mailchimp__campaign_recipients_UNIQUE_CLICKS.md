# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaign_recipients
## Column: UNIQUE_CLICKS

**Description:**
The unique number of emails clicked from campaign emails. If a given email to a user was clicked multiple times, it will only count once in this metric. This is the metric for clicks that is reported by Mailchimp. Set to 0 if NULL.

---

## Root Cause
**Wrong aggregation logic: SQL counts distinct timestamps instead of counting if the email was clicked (0 or 1 per email)**

### Incorrect SQL Logic
```sql
campaign_metrics AS (
    SELECT
        cr.campaign_id,
        cr.member_id,
        count(distinct case when ca.action = 'click' then ca.timestamp end) AS unique_clicks,
        ...
)
```

### Correct SQL Logic
```sql
campaign_metrics AS (
    SELECT
        cr.campaign_id,
        cr.member_id,
        CASE WHEN count(case when ca.action = 'click' then 1 end) > 0 THEN 1 ELSE 0 END AS unique_clicks,
        ...
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "If a given email to a user was clicked multiple times, it will only count once"
  * For a single email (campaign_id + member_id), this should be 0 or 1
  * 0 = not clicked, 1 = clicked (regardless of how many times)

* **What the SQL actually computes:**
  * Counts distinct timestamps of click events
  * If user clicked 3 links at different timestamps, returns 3
  * Should return 1 (email was clicked)

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | # of Clicks | Distinct Timestamps | GT UNIQUE_CLICKS | Pred UNIQUE_CLICKS |
| --------- | ----------- | ------------------- | ---------------- | ------------------ |
| 37cc8cad6a75f018d69632984d8caf38 | 3 | 3 | 1 | 3 |
| f5114e6e6bb39e07781d2f51f409a7fe | 2 | 2 | 1 | 2 |

**Impact:**
* Current implementation: **8/10 matches (80%)**
* Corrected implementation: **10/10 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix is to change from counting distinct timestamps to a binary 0/1 based on whether any clicks occurred.
