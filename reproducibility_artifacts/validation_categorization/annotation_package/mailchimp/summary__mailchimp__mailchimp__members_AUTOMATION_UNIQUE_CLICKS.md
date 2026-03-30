# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__members
## Column: AUTOMATION_UNIQUE_CLICKS

**Description:**
The unique number of emails clicked from automation emails. If a given email to a user was clicked multiple times, it will only count once in this metric. This is the metric for clicks that is reported by Mailchimp. Set to 0 if NULL.

---

## Root Cause
**Wrong aggregation granularity: SQL aggregates by member_id only, but members can be in multiple lists**

### Incorrect SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        count(distinct case when aa.action = 'click' then aa.automation_email_id || '-' || aa.member_id end) AS automation_unique_clicks,
        ...
    GROUP BY ar.member_id  -- WRONG
)
```

### Correct SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        ar.list_id,
        count(distinct case when aa.action = 'click' then aa.automation_email_id end) AS automation_unique_clicks,
        ...
    GROUP BY ar.member_id, ar.list_id  -- CORRECT
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unique automation emails clicked per member-list combination

* **What the SQL actually computes:**
  * Totals unique clicks across all lists

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | List ID | GT Unique Clicks | Predicted Unique Clicks |
| --------- | ------- | ---------------- | ----------------------- |
| 4956ae6c75... | 8e423a4179 | 1 | 2 |
| 4956ae6c75... | 8e423a4180 | 1 | 2 |

**Impact:**
* Current implementation: **7/9 matches (77.8%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires grouping by (member_id, list_id).
