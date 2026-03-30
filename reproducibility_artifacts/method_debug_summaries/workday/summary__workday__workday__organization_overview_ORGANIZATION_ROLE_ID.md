# Column Mismatch Summary

## Database: workday
## Table: workday__organization_overview
## Column: ORGANIZATION_ROLE_ID

**Description:**
The role id associated with the organization.

---

## Root Cause
**SQL uses wrong table: `organization_role_worker.role_id` instead of `organization_role.role_id`**

### Incorrect SQL Logic
```sql
SELECT
    o.id AS organization_id,
    orw.role_id AS organization_role_id,  -- Uses organization_role_worker!
    ...
FROM organization o
LEFT JOIN organization_role_worker orw ON o.id = orw.organization_id
LEFT JOIN organization_role orl ON orw.role_id = orl.role_id AND orw.organization_id = orl.organization_id
```

### Correct SQL Logic
```sql
SELECT
    o.id AS organization_id,
    orl.role_id AS organization_role_id,  -- Uses organization_role directly!
    ...
FROM organization o
LEFT JOIN organization_role orl ON o.id = orl.organization_id
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "The role id associated with the organization"
* **What the SQL computes**: The role_id from `organization_role_worker` table (worker-specific role assignments)
* **What the GT expects**: The role_id from `organization_role` table (organization-level role definitions)

The `organization_role` table has:
- `organization_id` = the organization
- `role_id` = **same as organization_id** (they're equal!)
- `organization_role_code` = "Absence_Partner"

The `organization_role_worker` table has:
- `organization_id` = the organization
- `role_id` = **different worker-specific role IDs** (not equal to organization_id)
- Links workers to roles within organizations

The SQL uses `organization_role_worker.role_id` which returns different values than expected.

---

## Evidence

**Key comparison demonstrating the error:**

| Organization ID | Wrong (orw.role_id) | Correct (orl.role_id) | Ground Truth |
| --------------- | ------------------- | --------------------- | ------------ |
| 64a64b71dcec4ecca7c5ff134c8697ce | 41b4436b31f0464ca720bc7809971ded | 64a64b71dcec4ecca7c5ff134c8697ce | 64a64b71dcec4ecca7c5ff134c8697ce |
| 89e47473254c018ca67096f0d0447c00 | b0066a92b537440b9c7eaed30f18a67a | 89e47473254c018ca67096f0d0447c00 | 89e47473254c018ca67096f0d0447c00 |
| 9378b36dabd94cc391ef5392166aa00e | 041d606550cc1069b5283ba34c0b9982 | 9378b36dabd94cc391ef5392166aa00e | 9378b36dabd94cc391ef5392166aa00e |
| 98aba7979690012a84c95af32b057201 | 041d606550cc1069b5283ba34c0b9982 | 98aba7979690012a84c95af32b057201 | 98aba7979690012a84c95af32b057201 |
| f62f2721e8194dfc9c6feb74cd8eb271 | 5bcec92217ec4294a850597460eec8ed | f62f2721e8194dfc9c6feb74cd8eb271 | f62f2721e8194dfc9c6feb74cd8eb271 |

**Key pattern:**
- GT shows `ORGANIZATION_ROLE_ID = ORGANIZATION_ID` (they're the same!)
- This matches `organization_role.role_id` which equals `organization_role.organization_id`
- SQL incorrectly returns worker-specific role IDs from `organization_role_worker`

**Source table comparison:**

| Table | organization_id | role_id |
| ----- | --------------- | ------- |
| organization_role | 64a64b71dcec4ecca7c5ff134c8697ce | 64a64b71dcec4ecca7c5ff134c8697ce |
| organization_role_worker | 64a64b71dcec4ecca7c5ff134c8697ce | 41b4436b31f0464ca720bc7809971ded |

**Impact:**
* Current implementation: **0/5 matches (0%)**
* Corrected implementation: **5/5 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The `organization_role` table defines organization-level roles where `role_id = organization_id`. The `organization_role_worker` table assigns workers to roles and has different role_id values. The SQL incorrectly uses the worker-specific role IDs instead of the organization-level role IDs.

**Organizations with correct role_id (equals org_id):**
- 64a64b71dcec4ecca7c5ff134c8697ce (Planning & Analysis)
- 89e47473254c018ca67096f0d0447c00 (Call Center - Nordics)
- 9378b36dabd94cc391ef5392166aa00e (Executive Management)
- 98aba7979690012a84c95af32b057201 (Call Center - Benelux)
- f62f2721e8194dfc9c6feb74cd8eb271 (Marketing)
