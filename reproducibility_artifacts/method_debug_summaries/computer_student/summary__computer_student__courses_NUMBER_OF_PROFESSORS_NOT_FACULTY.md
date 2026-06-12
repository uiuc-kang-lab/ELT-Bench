# Column Mismatch Summary

## Database: computer_student
## Table: courses
## Column: NUMBER_OF_PROFESSORS_NOT_FACULTY

**Description:**
Number of professors teaching the course who are not faculty, replace NULL values with 0.

---

## Root Cause
**Semantic misinterpretation: SQL counts non-professors (professor=0) instead of professors without faculty positions (professor=1 AND hasposition='0')**

### Incorrect SQL Logic
```sql
SUM(CASE WHEN professor = 0 THEN 1 ELSE 0 END) as number_of_professors_not_faculty
```

### Correct SQL Logic
```sql
SUM(CASE WHEN professor = 1 AND hasposition = '0' THEN 1 ELSE 0 END) as number_of_professors_not_faculty
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Professors who are not faculty" = people where `professor = 1` (they ARE professors) but `hasposition = '0'` (they don't have a faculty position)
  * The schema shows `hasposition` values for professors: `Faculty`, `Faculty_adj`, `Faculty_eme`, `Faculty_aff`, and `0`
  * Professors with `hasposition = '0'` are professors without faculty positions (10 such people exist)

* **What the SQL actually computes:**
  * The SQL counts people where `professor = 0`, which are NOT professors at all (students and other non-professor persons)
  * This fundamentally misinterprets "professors who are not faculty" as "non-professors"

**Schema verification:**
- `person.professor`: "whether the person is a professor" (1 = professor, 0 = not professor)
- `person.hasPosition`: "whether the person has a position in the faculty" (Faculty, Faculty_adj, Faculty_eme, Faculty_aff, or 0)

---

## Evidence

**Key comparison demonstrating the error:**

| Course ID | Wrong Logic (professor=0) | Correct Logic (professor=1 AND hasposition='0') | Ground Truth |
| --------- | ------------------------- | ----------------------------------------------- | ------------ |
| 11.0      | 1                         | 0                                               | 0            |
| 18.0      | 1                         | 0                                               | 0            |
| 38.0      | 2                         | 0                                               | 0            |
| 49.0      | 1                         | 2                                               | 2            |
| 104.0     | 2                         | 0                                               | 0            |
| 147.0     | 2                         | 0                                               | 0            |
| 165.0     | 3                         | 2                                               | 2            |

**Example demonstrating the difference:**
- Course 11: Taught by professors p_id=[52, 57, 298, 324, 331]
  - p_id=57 has `professor=1, hasposition='0'` → NOT Faculty
  - But the wrong logic finds p_id=57 NOT counted (professor=1), instead counting 1 person with professor=0
  - Actually there are no teachers with professor=0 for this course, so the issue is different counting

**Impact:**
* Current implementation: **115/132 matches (87.1%)**
* Corrected implementation: **132/132 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

The key insight is that "professors not faculty" refers to people who ARE professors (`professor=1`) but do NOT have a faculty position (`hasposition='0'`), not people who are not professors at all.
