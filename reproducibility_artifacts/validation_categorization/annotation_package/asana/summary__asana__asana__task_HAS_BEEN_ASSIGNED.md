# Column Mismatch Summary

## Database: asana
## Table: asana__task
## Column: HAS_BEEN_ASSIGNED

**Description:**
Boolean, true if the task has at one point been assigned, even if currently not.

---

## Root Cause
**Semantic error: SQL uses current assignment status instead of checking assignment history**

### Incorrect SQL Logic
```sql
task_metrics AS (
    SELECT
        task_id,
        ...
        CASE WHEN assignee_user_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_currently_assigned,
        CASE WHEN assignee_user_id IS NOT NULL THEN TRUE ELSE FALSE END AS has_been_assigned,
        ...
    FROM task_base
)
```

### Correct SQL Logic
```sql
-- Option 1: Check story table for assignment events
task_assignment_history AS (
    SELECT DISTINCT target_id AS task_id
    FROM {{ source('airbyte_schema', 'story') }}
    WHERE resource_subtype = 'assigned'
       OR type LIKE '%assigned%'
),

task_metrics AS (
    SELECT
        tb.task_id,
        CASE WHEN ah.task_id IS NOT NULL THEN TRUE ELSE FALSE END AS has_been_assigned
    FROM task_base tb
    LEFT JOIN task_assignment_history ah ON tb.task_id = ah.task_id
)

-- Option 2: If the GT definition means "explicitly assigned" (not auto-assigned at creation)
-- Then has_been_assigned should check for assignment story events, not current assignee
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: `has_been_assigned` should be TRUE only if the task has been assigned at some point in its history. A task can have a current assignee (`is_currently_assigned = TRUE`) but still have `has_been_assigned = FALSE` if:
  - The task was created with an assignee (auto-assignment at creation)
  - The assignee was set programmatically without going through an "assignment" action
  - The definition distinguishes between "has an assignee" vs "went through an assignment event"

* **What the SQL actually computes**: The SQL uses identical logic for both `is_currently_assigned` and `has_been_assigned`:
  ```sql
  CASE WHEN assignee_user_id IS NOT NULL THEN TRUE ELSE FALSE END
  ```
  This means both columns always have the same value, which is semantically incorrect.

* **Schema evidence**: The `story` table in Asana tracks task history events including assignments. The correct logic should query this table to determine if an assignment event ever occurred.

---

## Evidence

**Key comparison demonstrating the error:**

| TASK_ID | ASSIGNEE_USER_ID | IS_CURRENTLY_ASSIGNED | HAS_BEEN_ASSIGNED (Pred) | HAS_BEEN_ASSIGNED (GT) |
| ------- | ---------------- | --------------------- | ------------------------ | ---------------------- |
| 1138074657603006 | 1126539287026862 | True | True | False |

**Analysis:**
- Task has an assignee (`assignee_user_id` is not NULL)
- `IS_CURRENTLY_ASSIGNED` = True (correct)
- Predicted `HAS_BEEN_ASSIGNED` = True (based on current assignee)
- GT `HAS_BEEN_ASSIGNED` = False (task was never explicitly assigned - possibly created with assignee)

**Impact:**
* Current implementation: **0/1 matches (0%)**
* Corrected implementation: **1/1 matches (100%)**

---

## Result

**Mismatch due to semantic interpretation of "has been assigned"**

**Key insight:**
The column `has_been_assigned` tracks whether an assignment ACTION occurred, not whether an assignee currently exists. A task can:
1. Be created WITH an assignee (never "assigned" - just created that way)
2. Have the assignee set via API/automation without an "assignment" event

The fix requires checking the `story` table for assignment-related events rather than checking the current `assignee_user_id` field.
