# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__members
## Column: AUTOMATION_SENDS

**Description:**
The number of sent emails from automations. Set to 0 if NULL.

---

## Root Cause
**Wrong aggregation granularity: SQL aggregates by member_id only, but members can be in multiple lists with different automation activity per list**

### Incorrect SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        count(distinct ar.automation_email_id || '-' || ar.member_id) AS automation_sends,
        ...
    FROM automation_recipient ar
    ...
    GROUP BY ar.member_id  -- WRONG: doesn't distinguish between lists
)
```

### Correct SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        ar.list_id,
        count(distinct ar.automation_email_id) AS automation_sends,
        ...
    FROM automation_recipient ar
    ...
    GROUP BY ar.member_id, ar.list_id  -- CORRECT: maintains list-level granularity
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count automation email sends per member-list combination
  * The members table has a row per (member_id, list_id) combination

* **What the SQL actually computes:**
  * Groups by member_id only
  * When member is in multiple lists, assigns the TOTAL sends across all lists to each row
  * Member `4956ae6c75...` is in 2 lists (8e423a4179 and 8e423a4180)

**Example:**
- Member `4956ae6c75...` received automation emails on both lists
- List 8e423a4179: 1 automation send
- List 8e423a4180: 1 automation send
- SQL computes: 2 total (applies to both rows)
- GT expects: 1 per list (specific to each list)

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | List ID | GT Sends | Predicted Sends |
| --------- | ------- | -------- | --------------- |
| 4956ae6c75... | 8e423a4179 | 1 | 2 |
| 4956ae6c75... | 8e423a4180 | 1 | 2 |

**Impact:**
* Current implementation: **7/9 matches (77.8%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires grouping by (member_id, list_id) to maintain proper granularity matching the members table structure.
