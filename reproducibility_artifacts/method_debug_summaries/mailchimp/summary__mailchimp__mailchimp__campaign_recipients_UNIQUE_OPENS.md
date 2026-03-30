# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaign_recipients
## Column: UNIQUE_OPENS

**Description:**
The unique number of emails opened from campaign emails. If a given email to a user was opened multiple times, it will only count once in this metric. This is the metric for opens that is reported by Mailchimp. Set to 0 if NULL.

---

## Root Cause
**Wrong aggregation logic: SQL counts distinct timestamps instead of counting if the email was opened (0 or 1 per email)**

### Incorrect SQL Logic
```sql
campaign_metrics AS (
    SELECT
        cr.campaign_id,
        cr.member_id,
        count(distinct case when ca.action = 'open' then ca.timestamp end) AS unique_opens,
        ...
)
```

### Correct SQL Logic
```sql
campaign_metrics AS (
    SELECT
        cr.campaign_id,
        cr.member_id,
        CASE WHEN count(case when ca.action = 'open' then 1 end) > 0 THEN 1 ELSE 0 END AS unique_opens,
        ...
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "If a given email to a user was opened multiple times, it will only count once"
  * For a single email (campaign_id + member_id), this should be 0 or 1
  * 0 = not opened, 1 = opened (regardless of how many times)

* **What the SQL actually computes:**
  * Counts distinct timestamps of open events
  * If user opened the email 3 times at different timestamps, returns 3
  * Should return 1 (since it's the same email, just opened multiple times)

**Example:**
- Member `31d6eef7ddb994d81380735289af2dfb` opened campaign `c2b4c1c0d9` at 3 different times
- GT: 1 (email was opened)
- Pred: 3 (counted 3 distinct timestamps)

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | # of Opens | Distinct Timestamps | GT UNIQUE_OPENS | Pred UNIQUE_OPENS |
| --------- | ---------- | ------------------- | --------------- | ----------------- |
| 31d6eef7ddb994d81380735289af2dfb | 3 | 3 | 1 | 3 |
| 37cc8cad6a75f018d69632984d8caf38 | 3 | 3 | 1 | 3 |
| f5114e6e6bb39e07781d2f51f409a7fe | 2 | 2 | 1 | 2 |

**Impact:**
* Current implementation: **7/10 matches (70%)**
* Corrected implementation: **10/10 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix is to change from counting distinct timestamps to a binary 0/1 based on whether any opens occurred. "Unique opens" in this context means "was this specific email opened" (binary), not "how many unique open events occurred".
