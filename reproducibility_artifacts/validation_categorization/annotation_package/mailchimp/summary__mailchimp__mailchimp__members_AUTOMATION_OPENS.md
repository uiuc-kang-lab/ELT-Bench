# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__members
## Column: AUTOMATION_OPENS

**Description:**
The number of open events from automation emails. The same email being opened multiple times is included in this metric. Set to 0 if NULL.

---

## Root Cause
**Wrong aggregation granularity: SQL aggregates by member_id only, but members can be in multiple lists**

### Incorrect SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        count(case when aa.action = 'open' then 1 end) AS automation_opens,
        ...
    FROM automation_recipient ar
    LEFT JOIN automation_activity aa ...
    GROUP BY ar.member_id  -- WRONG: doesn't distinguish between lists
)
```

### Correct SQL Logic
```sql
automation_metrics AS (
    SELECT
        ar.member_id,
        ar.list_id,
        count(case when aa.action = 'open' then 1 end) AS automation_opens,
        ...
    FROM automation_recipient ar
    LEFT JOIN automation_activity aa ...
    GROUP BY ar.member_id, ar.list_id  -- CORRECT: maintains list-level granularity
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count open events per member-list combination

* **What the SQL actually computes:**
  * Groups by member_id only
  * Assigns total opens across all lists to each member row
  * Member `4956ae6c75...` has different opens per list

---

## Evidence

**Key comparison demonstrating the error:**

| Member ID | List ID | GT Opens | Predicted Opens |
| --------- | ------- | -------- | --------------- |
| 4956ae6c75... | 8e423a4179 | 1 | 1 |
| 4956ae6c75... | 8e423a4180 | 0 | 1 |

**Impact:**
* Current implementation: **8/9 matches (88.9%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires grouping by (member_id, list_id).
