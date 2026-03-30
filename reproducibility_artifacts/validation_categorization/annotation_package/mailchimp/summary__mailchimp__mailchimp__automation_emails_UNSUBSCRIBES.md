# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__automation_emails
## Column: UNSUBSCRIBES

**Description:**
The number of users who have unsubscribed from campaign emails. Set to 0 if NULL.

---

## Root Cause
**Wrong join condition: SQL joins `unsubscribe.campaign_id = automation_email.automation_id` instead of `unsubscribe.campaign_id = automation_email.id`**

### Incorrect SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        ae.id AS automation_email_id,
        count(*) AS unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.automation_id  -- WRONG
    GROUP BY ae.id
)
```

### Correct SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        ae.id AS automation_email_id,
        count(*) AS unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.id  -- CORRECT
    GROUP BY ae.id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes per automation email

* **What the SQL actually computes:**
  * Joins on wrong column - `campaign_id = automation_id` finds no matches
  * The unsubscribe has `campaign_id = 'b63e7b8aff'`
  * This matches `automation_email.id`, not `automation_email.automation_id`

**Data mapping:**
- `unsubscribe.campaign_id = 'b63e7b8aff'`
- `automation_email.id = 'b63e7b8aff'` - MATCH
- `automation_email.automation_id = '71ad2ce945'` - NO MATCH

---

## Evidence

**Key comparison demonstrating the error:**

| Automation Email ID | GT UNSUBSCRIBES | Predicted UNSUBSCRIBES |
| ------------------- | --------------- | ---------------------- |
| b63e7b8aff | 1 | 0 |
| 123 | 0 | 0 |

**Impact:**
* Current implementation: **1/2 matches (50%)**
* Corrected implementation: **2/2 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing the join from `u.campaign_id = ae.automation_id` to `u.campaign_id = ae.id`.
