# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__automations
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
        ae.automation_id,
        count(*) AS unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.automation_id  -- WRONG: should join on ae.id
    GROUP BY ae.automation_id
)
```

### Correct SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        ae.automation_id,
        count(*) AS unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.id  -- CORRECT: unsubscribe.campaign_id matches automation_email.id
    GROUP BY ae.automation_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes from automation emails, aggregated at the automation level

* **What the SQL actually computes:**
  * Joins on `campaign_id = automation_id` - finds no matches
  * The unsubscribe has `campaign_id = 'b63e7b8aff'`
  * This matches `automation_email.id`, not `automation_id`

**Data structure:**
| Table | Column | Value |
| ----- | ------ | ----- |
| unsubscribe | campaign_id | 'b63e7b8aff' |
| automation_email | id | 'b63e7b8aff' |
| automation_email | automation_id | '71ad2ce945' |

---

## Evidence

**Key comparison demonstrating the error:**

| Automation ID | GT UNSUBSCRIBES | Predicted UNSUBSCRIBES |
| ------------- | --------------- | ---------------------- |
| 71ad2ce945 | 1 | 0 |
| 12345 | 0 | 0 |

**Impact:**
* Current implementation: **1/2 matches (50%)**
* Corrected implementation: **2/2 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing the join from `u.campaign_id = ae.automation_id` to `u.campaign_id = ae.id`.
