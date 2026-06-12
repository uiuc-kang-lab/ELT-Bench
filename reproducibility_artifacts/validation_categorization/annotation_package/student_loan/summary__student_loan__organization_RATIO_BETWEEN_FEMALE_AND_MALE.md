# Column Mismatch Summary

## Database: student_loan
## Table: organization
## Column: RATIO_BETWEEN_FEMALE_AND_MALE

**Description:**
The ratio between female and male students in the organization.

---

## Root Cause
**Inverted ratio calculation - computing female/male instead of male/female**

### Current SQL Logic (Incorrect)
```sql
female_count AS (
    SELECT
        os.organ,
        COUNT(DISTINCT os.name) - COUNT(DISTINCT m.name) AS num_female_students
    FROM org_students os
    LEFT JOIN male m ON os.name = m.name
    GROUP BY os.organ
)

CASE
    WHEN mc.num_male_students > 0 THEN (fc.num_female_students * 1.0 / mc.num_male_students)
    ELSE 0
END AS ratio_between_female_and_male
```

### Expected Logic
```sql
-- Ratio should be male/female or a different interpretation
-- GT values are < 1 when females > males, Pred values are > 1
CASE
    WHEN fc.num_female_students > 0 THEN (mc.num_male_students * 1.0 / fc.num_female_students)
    ELSE 0
END AS ratio_between_female_and_male
```

---

## Why This Is Wrong

* **What the column should compute:**
  * The ratio between male and female students (male/female)

* **What the SQL actually computes:**
  * female/male ratio

* **The issue:**
  * GT shows values like 0.65, 0.54, 0.53 (male/female ratio where males < females)
  * Pred shows values like 1.89, 1.19, 1.09 (female/male ratio, the inverse)
  * For air_force: GT=0.654, Pred=1.889 → 0.654 ≈ 1/1.889 (inverse relationship)

---

## Evidence

**Impact:**
* Current implementation: **0/7 matches (0%)**

| ORGAN | GT | Pred |
|-------|-----|------|
| air_force | 0.654 | 1.889 |
| army | 0.543 | 1.188 |
| fire_department | 0.526 | 1.094 |
| foreign_legion | 0.484 | 0.938 |
| marines | 0.355 | 0.550 |
| navy | 0.459 | 0.850 |
| peace_corps | 0.656 | 1.909 |

---

## Result

**Requires fix: Invert the ratio to compute male/female instead of female/male**

The SQL should compute `num_male_students / num_female_students` instead of `num_female_students / num_male_students`.
