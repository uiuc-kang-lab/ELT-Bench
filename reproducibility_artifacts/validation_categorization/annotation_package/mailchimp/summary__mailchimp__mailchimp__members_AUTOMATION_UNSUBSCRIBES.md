# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__members
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
        u.member_id,
        count(*) AS automation_unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.automation_id  -- WRONG
    GROUP BY u.member_id
)
```

### Correct SQL Logic
```sql
automation_unsubscribes AS (
    SELECT
        u.member_id,
        count(*) AS automation_unsubscribes
    FROM unsubscribe u
    INNER JOIN automation_email ae
        ON u.campaign_id = ae.id  -- CORRECT: campaign_id stores the email ID
    GROUP BY u.member_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes from automation emails per member

* **What the SQL actually computes:**
  * Joins on wrong column - `campaign_id = automation_id` finds no matches
  * The unsubscribe has `campaign_id = 'b63e7b8aff'`
  * This matches `automation_email.id`, not `automation_email.automation_id`

**Data verification:**
- `unsubscribe.campaign_id` = 'b63e7b8aff'
- `automation_email.id` values: ['b63e7b8aff', '123'] - MATCH
- `automation_email.automation_id` values: ['71ad2ce945', '12345'] - NO MATCH

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | campaign_id | Matches ae.id? | Matches ae.automation_id? | GT | Predicted |
| --------- | ----------- | -------------- | ------------------------- | -- | --------- |
| 4d1bf0aa67... | b63e7b8aff | Yes | No | 1 | 0 |

**Impact:**
* Current implementation: **8/9 matches (88.9%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing the join from `u.campaign_id = ae.automation_id` to `u.campaign_id = ae.id`.
