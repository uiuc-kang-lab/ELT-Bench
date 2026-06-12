# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__lists
## Column: AUTOMATION_UNSUBSCRIBES

**Description:**
The number of users who have unsubscribed from automation emails. Set to 0 if NULL.

---

## Root Cause
**Wrong join condition: SQL joins `unsubscribe.campaign_id = automation_email.automation_id` instead of `unsubscribe.campaign_id = automation_email.id`**

### Incorrect SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        u.list_id,
        count(*) AS automation_unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.automation_id  -- WRONG: campaign_id matches automation_email.id, not automation_id
    GROUP BY u.list_id
)
```

### Correct SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        u.list_id,
        count(*) AS automation_unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.id  -- CORRECT: unsubscribe.campaign_id matches automation_email.id
    GROUP BY u.list_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes that originated from **automation emails**
  * The `unsubscribe.campaign_id` contains the ID of the email (campaign or automation_email) that triggered the unsubscribe

* **What the SQL actually computes:**
  * Joins on `u.campaign_id = ae.automation_id`
  * The unsubscribe has `campaign_id = 'b63e7b8aff'`
  * But `automation_id` values are `['71ad2ce945', '12345']` - no match!
  * The `automation_email.id` values are `['b63e7b8aff', '123']` - this matches!

**Table structure clarification:**
| Table | Column | Values |
| ----- | ------ | ------ |
| unsubscribe | campaign_id | 'b63e7b8aff' |
| automation_email | id | 'b63e7b8aff', '123' |
| automation_email | automation_id | '71ad2ce945', '12345' |

---

## Evidence

**Key comparison demonstrating the error:**

| List ID | unsubscribe.campaign_id | Matches automation_email.id? | Matches automation_email.automation_id? | GT | Predicted |
| ------- | ----------------------- | ---------------------------- | --------------------------------------- | -- | --------- |
| 8e423a4179 | b63e7b8aff | Yes | No | 1 | 0 |
| 8e423a4180 | (none) | N/A | N/A | 0 | 0 |

**Impact:**
* Current implementation: **1/2 matches (50%)**
* Corrected implementation: **2/2 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix is to change the join condition from `u.campaign_id = ae.automation_id` to `u.campaign_id = ae.id`. The `unsubscribe.campaign_id` field stores the ID of the email (which can be either a campaign ID or an automation_email ID), not the automation's ID.
