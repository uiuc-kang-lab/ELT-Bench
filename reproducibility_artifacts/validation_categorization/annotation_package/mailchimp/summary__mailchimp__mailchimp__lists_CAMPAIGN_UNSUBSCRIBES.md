# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__lists
## Column: CAMPAIGN_UNSUBSCRIBES

**Description:**
The number of users who have unsubscribed from campaign emails. Set to 0 if NULL.

---

## Root Cause
**Wrong join condition: SQL counts all unsubscribes instead of only campaign-related unsubscribes**

### Incorrect SQL Logic
```sql
campaign_unsubscribes AS (
    SELECT
        list_id,
        count(*) AS campaign_unsubscribes
    FROM unsubscribe
    GROUP BY list_id
)
```

### Correct SQL Logic
```sql
campaign_unsubscribes AS (
    SELECT
        u.list_id,
        count(*) AS campaign_unsubscribes
    FROM unsubscribe u
    INNER JOIN campaign c ON u.campaign_id = c.id
    GROUP BY u.list_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count unsubscribes that originated from **campaign emails** only
  * Should NOT include unsubscribes from automation emails

* **What the SQL actually computes:**
  * Counts ALL unsubscribes in the unsubscribe table for each list
  * The `unsubscribe.campaign_id` field contains BOTH campaign IDs AND automation_email IDs
  * Without filtering, automation email unsubscribes are incorrectly included

**Key data insight:**
The unsubscribe table has `campaign_id = 'b63e7b8aff'`:
- This ID is NOT in the `campaign` table (campaign ID is `c2b4c1c0d9`)
- This ID IS in the `automation_email.id` column
- Therefore, this unsubscribe is from an automation email, not a campaign

---

## Evidence

**Key comparison demonstrating the error:**

| List ID | Unsubscribe campaign_id | Is Campaign? | Is Automation Email? | GT | Predicted |
| ------- | ----------------------- | ------------ | -------------------- | -- | --------- |
| 8e423a4179 | b63e7b8aff | No | Yes | 0 | 1 |
| 8e423a4180 | (none) | N/A | N/A | 0 | 0 |

**Data verification:**
- `campaign.id` values: `['c2b4c1c0d9']`
- `automation_email.id` values: `['b63e7b8aff', '123']`
- `unsubscribe.campaign_id` value: `'b63e7b8aff'` (matches automation_email, not campaign)

**Impact:**
* Current implementation: **1/2 matches (50%)**
* Corrected implementation: **2/2 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix is to join the unsubscribe table with the campaign table to ensure only campaign-related unsubscribes are counted. The single unsubscribe in the data is from automation email `b63e7b8aff`, not from any campaign.
