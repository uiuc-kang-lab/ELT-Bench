# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__members
## Column: CAMPAIGN_UNSUBSCRIBES

**Description:**
The number of users who have unsubscribed from campaign emails. Set to 0 if NULL.

---

## Root Cause
**Wrong source: SQL counts all unsubscribes instead of filtering for campaign-only unsubscribes**

### Incorrect SQL Logic
```sql
campaign_unsubscribes AS (
    SELECT
        member_id,
        count(*) AS campaign_unsubscribes
    FROM unsubscribe
    GROUP BY member_id
)
```

### Correct SQL Logic
```sql
campaign_unsubscribes AS (
    SELECT
        u.member_id,
        count(*) AS campaign_unsubscribes
    FROM unsubscribe u
    INNER JOIN campaign c ON u.campaign_id = c.id
    GROUP BY u.member_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes from **campaign emails** only for each member

* **What the SQL actually computes:**
  * Counts ALL unsubscribes for each member
  * Includes automation email unsubscribes incorrectly
  * The `unsubscribe.campaign_id = 'b63e7b8aff'` is an automation_email.id, not a campaign.id

**Data verification:**
- Member `4d1bf0aa67...` has 1 unsubscribe with campaign_id = 'b63e7b8aff'
- This ID matches `automation_email.id`, NOT `campaign.id`
- Therefore, this is an automation unsubscribe, not a campaign unsubscribe

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | Unsubscribe campaign_id | Is Campaign? | GT | Predicted |
| --------- | ----------------------- | ------------ | -- | --------- |
| 4d1bf0aa67... | b63e7b8aff | No (automation_email) | 0 | 1 |

**Impact:**
* Current implementation: **8/9 matches (88.9%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires joining with the campaign table to ensure only campaign-related unsubscribes are counted.
