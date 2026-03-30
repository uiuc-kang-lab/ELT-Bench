# Column Mismatch Summary

## Database: workday
## Table: workday__employee_overview
## Columns: ALL 30 COLUMNS

**Description:**
Each record represents an employee with enriched personal information and the positions they hold. This model provides employee demographic and geographical distribution, overall retention and turnover, and compensation analysis.

---

## Root Cause
**Multiple issues: (1) Fan-out from organization join creates duplicate rows, (2) FIRST_NAME hardcoded to NULL, (3) POSITION_LOCATION join path fails**

The issues affect ALL 30 columns because:
1. **Duplicate rows** cause row count mismatch (GT: 5 rows, Predicted: 9 rows)
2. **FIRST_NAME** is explicitly NULL in SQL
3. **POSITION_LOCATION** is NULL due to join path failure

### Incorrect SQL Logic

**Issue 1: Duplicate rows from worker_position_org_history join**
```sql
FROM worker_history wh
LEFT JOIN worker_position_history wph
    ON wh.id = wph.worker_id
LEFT JOIN worker_position_org_history wpoh
    ON wph.position_id = wpoh.position_id
    AND wph.worker_id = wpoh.worker_id  -- This creates fan-out!
LEFT JOIN organization org
    ON wpoh.organization_id = org.id
```

**Issue 2: FIRST_NAME hardcoded to NULL**
```sql
CAST(NULL AS VARCHAR) AS first_name
```

**Issue 3: POSITION_LOCATION uses wrong source**
```sql
org.location AS position_location  -- Joins via worker_position_org_history which fails
```

### Correct SQL Logic

**Issue 1: Remove or deduplicate the organization join**
```sql
-- Option A: Remove the join entirely if not needed
FROM worker_history wh
LEFT JOIN worker_position_history wph
    ON wh.id = wph.worker_id

-- Option B: Use DISTINCT or ROW_NUMBER to deduplicate
WITH wpoh_deduped AS (
    SELECT DISTINCT position_id, worker_id, organization_id
    FROM worker_position_org_history
    WHERE used_in_change_organization_assignments = True  -- Filter to primary org
)
```

**Issue 2: Join person_name table for first_name**
```sql
wh.compensation_grade_profile_id AS first_name  -- GT shows this is the expected value
-- OR join person_name if actual names are needed
```

**Issue 3: Use worker_position_history for location**
```sql
wph.business_site_summary_local AS position_location  -- Has values: Sydney, Melbourne
```

---

## Why the Original Logic Is Wrong

**Issue 1: Duplicate Rows**
* **What the GT expects**: 5 unique employee records (one per worker+position combination)
* **What the SQL computes**: 9 rows due to fan-out from worker_position_org_history join
* The worker_position_org_history table has multiple rows per position+worker (e.g., employee `e8b872e604ad0b1acc5aa6b1587d2a8b` has 5 organization associations)
* This causes 5 duplicate rows for that single employee

**Issue 2: FIRST_NAME**
* **What the column description says**: "The first name of the individual"
* **What the SQL computes**: Always NULL (hardcoded)
* **What the GT expects**: The `compensation_grade_profile_id` value from worker_history

**Issue 3: POSITION_LOCATION**
* **What the column description says**: "The position location of the employee"
* **What the SQL computes**: NULL (organization.location via failed join path)
* **What the GT expects**: Values like "Sydney", "Melbourne" from worker_position_history.business_site_summary_local

---

## Evidence

**Key comparison demonstrating duplicate rows:**

| EMPLOYEE_ID | GT Rows | Predicted Rows |
| ----------- | ------- | -------------- |
| 46a61ac1b765c4b94ff2d972434630ec | 1 | 1 |
| 4dba4efbb8e1cc4a103f5c90bf21d6ac | 1 | 1 |
| 4eb92539f4f6e475355421d202b3269b | 1 | 1 |
| 66a5c521e0098480936ff0edaf49e5fb | 1 | 1 |
| e8b872e604ad0b1acc5aa6b1587d2a8b | 1 | **5** |
| **Total** | **5** | **9** |

**Key comparison for FIRST_NAME:**

| EMPLOYEE_ID | Wrong (NULL) | Correct (compensation_grade_profile_id) | Ground Truth |
| ----------- | ------------ | --------------------------------------- | ------------ |
| 46a61ac1b765c4b94ff2d972434630ec | NULL | bfb3bb774248467cb761d73cb00bc162 | bfb3bb774248467cb761d73cb00bc162 |
| 4dba4efbb8e1cc4a103f5c90bf21d6ac | NULL | f8a88a8d5c5e494d853d8d28f9b11a06 | f8a88a8d5c5e494d853d8d28f9b11a06 |
| 66a5c521e0098480936ff0edaf49e5fb | NULL | 3d3fdfacbec54de68c342d32771cb4db | 3d3fdfacbec54de68c342d32771cb4db |
| e8b872e604ad0b1acc5aa6b1587d2a8b | NULL | 7860993be8d8100f8ad5ad2f8bdd106c | 7860993be8d8100f8ad5ad2f8bdd106c |

**Key comparison for POSITION_LOCATION:**

| EMPLOYEE_ID | Wrong (org.location) | Correct (business_site_summary_local) | Ground Truth |
| ----------- | -------------------- | ------------------------------------- | ------------ |
| 46a61ac1b765c4b94ff2d972434630ec | NULL | Sydney | Sydney |
| 4dba4efbb8e1cc4a103f5c90bf21d6ac | NULL | Sydney | Sydney |
| 4eb92539f4f6e475355421d202b3269b | NULL | Melbourne | Melbourne |
| 66a5c521e0098480936ff0edaf49e5fb | NULL | Sydney | Sydney |
| e8b872e604ad0b1acc5aa6b1587d2a8b | NULL | Sydney | Sydney |

**Impact:**
* Current implementation: **Row count mismatch (5 vs 9 rows)**, FIRST_NAME 1/5 matches (20%), POSITION_LOCATION 0/5 matches (0%)
* Corrected implementation: **5/5 rows, 100% match on all columns**

---

## Result

**Perfect match achievable with corrected logic**

**Key fixes needed:**

1. **Remove or deduplicate worker_position_org_history join** to eliminate duplicate rows
2. **Use `wh.compensation_grade_profile_id AS first_name`** instead of `CAST(NULL AS VARCHAR)`
3. **Use `wph.business_site_summary_local AS position_location`** instead of `org.location`

**Affected columns (all 30):**
- Due to duplicate rows: ALL columns affected
- FIRST_NAME: Directly affected (NULL vs actual value)
- POSITION_LOCATION: Directly affected (NULL vs actual value)

**The 5 employees with correct data:**
- 46a61ac1b765c4b94ff2d972434630ec (sflores, HR Manager, Sydney)
- 4dba4efbb8e1cc4a103f5c90bf21d6ac (egomes, Senior Manager Marketing Communications, Sydney)
- 4eb92539f4f6e475355421d202b3269b (rsandeep, Senior Customer Services Representative, Melbourne)
- 66a5c521e0098480936ff0edaf49e5fb (dconnors, Manager Global Support, Sydney)
- e8b872e604ad0b1acc5aa6b1587d2a8b (lchin, Customer Service Representative, Sydney)
