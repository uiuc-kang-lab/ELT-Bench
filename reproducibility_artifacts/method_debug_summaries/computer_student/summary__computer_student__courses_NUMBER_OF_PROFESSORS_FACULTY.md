# Column Mismatch Summary

## Database: computer_student
## Table: courses
## Column: NUMBER_OF_PROFESSORS_FACULTY

**Description:**
Number of professors teaching the course who are faculty, replace NULL values with 0.

---

## Root Cause
**Incomplete hasposition matching: SQL only matches 'Faculty' and 'Faculty_adj', missing 'Faculty_eme' and 'Faculty_aff' positions**

### Incorrect SQL Logic
```sql
SUM(CASE WHEN professor = 1 AND (hasposition = 'Faculty' OR hasposition = 'Faculty_adj') THEN 1 ELSE 0 END) as number_of_professors_faculty
```

### Correct SQL Logic
```sql
SUM(CASE WHEN professor = 1 AND hasposition LIKE 'Faculty%' THEN 1 ELSE 0 END) as number_of_professors_faculty
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Professors who are faculty" = people where `professor = 1` AND they have a faculty position
  * All faculty positions in the schema start with "Faculty": `Faculty`, `Faculty_adj`, `Faculty_eme`, `Faculty_aff`

* **What the SQL actually computes:**
  * The SQL only checks for `hasposition IN ('Faculty', 'Faculty_adj')`
  * This misses `Faculty_eme` (Faculty Emeritus, 3 people) and `Faculty_aff` (Faculty Affiliate, 3 people)
  * These 6 professors with Faculty_eme/Faculty_aff positions are incorrectly excluded

**Schema verification:**
- `person.professor`: "whether the person is a professor" (1 = professor)
- `person.hasPosition`: "whether the person has a position in the faculty"
  - Observed values: `Faculty` (40), `Faculty_adj` (6), `Faculty_eme` (3), `Faculty_aff` (3), `0` (10)

---

## Evidence

**Key comparison demonstrating the error:**

| Course ID | Wrong Logic (Faculty/Faculty_adj) | Correct Logic (LIKE 'Faculty%') | Ground Truth |
| --------- | --------------------------------- | ------------------------------- | ------------ |
| 8.0       | 0                                 | 1                               | 1            |
| 15.0      | 0                                 | 1                               | 1            |
| 18.0      | 4                                 | 5                               | 5            |
| 21.0      | 0                                 | 1                               | 1            |
| 44.0      | 2                                 | 3                               | 3            |
| 48.0      | 2                                 | 3                               | 3            |
| 98.0      | 0                                 | 1                               | 1            |
| 116.0     | 0                                 | 1                               | 1            |

**Example demonstrating the difference:**
- Course 8: Taught by p_id=297
  - p_id=297 has `professor=1, hasposition='Faculty_eme'`
  - Wrong logic: hasposition NOT IN ('Faculty', 'Faculty_adj') → count = 0
  - Correct logic: hasposition LIKE 'Faculty%' → count = 1
  - GT = 1

- Course 21: Taught by p_id=[22, 99]
  - p_id=22 has `professor=1, hasposition='Faculty_eme'`
  - p_id=99 has `professor=0` (not a professor)
  - Wrong logic: 0 (neither matches Faculty/Faculty_adj)
  - Correct logic: 1 (p_id=22 matches Faculty%)
  - GT = 1

**Impact:**
* Current implementation: **124/132 matches (93.9%)**
* Corrected implementation: **132/132 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

The key insight is that ALL faculty positions follow the pattern `Faculty%`, including:
- `Faculty` (regular faculty)
- `Faculty_adj` (adjunct faculty)
- `Faculty_eme` (emeritus faculty)
- `Faculty_aff` (affiliate faculty)

Using `hasposition LIKE 'Faculty%'` correctly captures all faculty members.
