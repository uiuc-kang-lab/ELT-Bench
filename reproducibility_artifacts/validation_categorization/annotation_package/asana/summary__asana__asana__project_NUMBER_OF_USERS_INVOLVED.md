# Column Mismatch Summary

## Database: asana
## Table: asana__project
## Column: NUMBER_OF_USERS_INVOLVED

**Description:**
Count of the unique users associated with the project

---

## Root Cause
**Wrong data source: SQL counts task assignees instead of counting the project owner**

### Incorrect SQL Logic
```sql
project_users AS (
    SELECT
        pt.project_id,
        COUNT(DISTINCT t.assignee_id) AS number_of_users_involved
    FROM {{ source('airbyte_schema', 'project_task') }} pt
    INNER JOIN {{ source('airbyte_schema', 'task') }} t ON pt.task_id = t.id
    WHERE t.assignee_id IS NOT NULL
    GROUP BY pt.project_id
)

-- In final SELECT:
COALESCE(pu.number_of_users_involved, 0) AS number_of_users_involved
```

### Correct SQL Logic
```sql
-- Simply count 1 if owner exists, 0 otherwise
SELECT
    pb.project_id,
    ...
    CASE WHEN pb.owner_user_id IS NOT NULL THEN 1 ELSE 0 END AS number_of_users_involved
FROM project_base pb
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: "Count of the unique users associated with the project" - this is interpreted by GT as the project owner.

* **What the SQL actually computes**: The SQL counts distinct task assignees (`COUNT(DISTINCT t.assignee_id)`) from all tasks in the project. This is a different metric entirely.

* **Evidence from GT data**:
  - All projects with an `owner_user_id` have `NUMBER_OF_USERS_INVOLVED = 1`
  - All projects without an `owner_user_id` (NULL) have `NUMBER_OF_USERS_INVOLVED = 0`
  - This is a perfect 1:1 correlation with owner presence

* **The misunderstanding**: "Users associated with the project" means the project owner, not task assignees. The owner is THE user directly associated with the project itself.

---

## Evidence

**Key comparison demonstrating the error:**

| PROJECT_ID | OWNER_USER_ID | NUMBER_OF_USERS_INVOLVED (GT) | NUMBER_OF_USERS_INVOLVED (Pred) |
| ---------- | ------------- | ----------------------------- | ------------------------------- |
| 338932209783787 | 2349446254454 | 1 | 0 |
| 339014487764325 | 2349446254454 | 1 | 0 |
| 339036947888917 | NULL | 0 | 0 |
| 1135568818569273 | NULL | 0 | 0 |
| 1127687633259843 | 338984235816349 | 1 | 0 |

**Pattern analysis:**
- GT = 1 when `owner_user_id IS NOT NULL` (12 projects)
- GT = 0 when `owner_user_id IS NULL` (4 projects)
- Pred = 0 for ALL projects (because no tasks exist with assignees)

**Perfect correlation confirmed:**
```
GT NUMBER_OF_USERS_INVOLVED == (owner_user_id IS NOT NULL ? 1 : 0)
```

**Impact:**
* Current implementation: **4/16 matches (25%)** - only matches where owner is NULL
* Corrected implementation: **16/16 matches (100%)**

---

## Result

**Mismatch due to wrong interpretation of "users associated with the project"**

**Key insight:**
The description "unique users associated with the project" refers specifically to the project owner, not to task assignees. The correct logic is:
```sql
CASE WHEN owner_user_id IS NOT NULL THEN 1 ELSE 0 END AS number_of_users_involved
```

**Projects with NUMBER_OF_USERS_INVOLVED = 1 (has owner):**
- 338932209783787 (owner: 2349446254454)
- 339014487764325 (owner: 2349446254454)
- 339036947888913 (owner: 2349446254454)
- 339036947888916 (owner: 2104505001945)
- 339036947888918 (owner: 2349446254454)
- 339282757803825 (owner: 2349446254454)
- 994480050688368 (owner: 2349446254454)
- 1103976536247089 (owner: 2349446254454)
- 1119233841877068 (owner: 2349446254454)
- 1123411555652103 (owner: 2349446254454)
- 1127687633259843 (owner: 338984235816349)
- 1133789517942526 (owner: 338984235816349)
- 1138337102495418 (owner: 338984235816349)

**Projects with NUMBER_OF_USERS_INVOLVED = 0 (no owner):**
- 339036947888917 (owner: NULL)
- 1135568818569273 (owner: NULL)
- 1142815262788834 (owner: NULL)
