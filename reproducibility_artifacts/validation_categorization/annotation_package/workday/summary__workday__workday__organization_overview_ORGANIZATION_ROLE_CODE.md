# Column Mismatch Summary

## Database: workday
## Table: workday__organization_overview
## Column: ORGANIZATION_ROLE_CODE

**Description:**
Code assigned to the organization role for reference and categorization.

---

## Root Cause
**JOIN condition fails because SQL uses mismatched role_ids from different tables**

### Incorrect SQL Logic
```sql
SELECT
    ...
    orl.organization_role_code
FROM organization o
LEFT JOIN organization_role_worker orw ON o.id = orw.organization_id
LEFT JOIN organization_role orl ON orw.role_id = orl.role_id AND orw.organization_id = orl.organization_id
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
                                    -- orw.role_id != orl.role_id, so JOIN fails!
```

### Correct SQL Logic
```sql
SELECT
    ...
    orl.organization_role_code
FROM organization o
LEFT JOIN organization_role orl ON o.id = orl.organization_id
-- Direct join without going through organization_role_worker
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "Code assigned to the organization role for reference and categorization"
* **What the SQL computes**: NULL (join fails because role_ids don't match)
* **What the GT expects**: "Absence_Partner" for all organizations

The SQL joins:
1. `organization` → `organization_role_worker` on `organization_id` ✓
2. `organization_role_worker` → `organization_role` on `role_id` **✗ FAILS**

The join fails because:
- `organization_role_worker.role_id` = worker-specific IDs (e.g., `41b4436b31f0464ca720bc7809971ded`)
- `organization_role.role_id` = organization IDs (e.g., `64a64b71dcec4ecca7c5ff134c8697ce`)
- These never match, so `organization_role_code` is always NULL

The fix is to join `organization_role` directly on `organization_id` without going through `organization_role_worker`.

---

## Evidence

**Key comparison demonstrating the error:**

| Organization ID | Organization Name | Wrong Logic | Correct Logic | Ground Truth |
| --------------- | ----------------- | ----------- | ------------- | ------------ |
| 64a64b71dcec4ecca7c5ff134c8697ce | Planning & Analysis | NULL | Absence_Partner | Absence_Partner |
| 89e47473254c018ca67096f0d0447c00 | Call Center - Nordics | NULL | Absence_Partner | Absence_Partner |
| 9378b36dabd94cc391ef5392166aa00e | Executive Management | NULL | Absence_Partner | Absence_Partner |
| 98aba7979690012a84c95af32b057201 | Call Center - Benelux | NULL | Absence_Partner | Absence_Partner |
| f62f2721e8194dfc9c6feb74cd8eb271 | Marketing | NULL | Absence_Partner | Absence_Partner |

**Why the join fails:**

| organization_id | orw.role_id | orl.role_id | Match? |
| --------------- | ----------- | ----------- | ------ |
| 64a64b71dcec4ecca7c5ff134c8697ce | 41b4436b31f0464ca720bc7809971ded | 64a64b71dcec4ecca7c5ff134c8697ce | **NO** |
| 89e47473254c018ca67096f0d0447c00 | b0066a92b537440b9c7eaed30f18a67a | 89e47473254c018ca67096f0d0447c00 | **NO** |
| 9378b36dabd94cc391ef5392166aa00e | 041d606550cc1069b5283ba34c0b9982 | 9378b36dabd94cc391ef5392166aa00e | **NO** |

The role_ids from `organization_role_worker` are completely different from `organization_role`, causing the LEFT JOIN to return NULL for `organization_role_code`.

**Impact:**
* Current implementation: **0/5 matches (0%)**
* Corrected implementation: **5/5 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The SQL's join path through `organization_role_worker` is incorrect. The `organization_role` table should be joined directly on `organization_id` to retrieve the `organization_role_code`. The intermediate join through `organization_role_worker` uses incompatible role_ids that never match.

**All organizations have:**
- `ORGANIZATION_ROLE_CODE = "Absence_Partner"`
