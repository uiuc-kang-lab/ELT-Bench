# Column Mismatch Summary

## Database: computer_student
## Table: courses
## Column: TAUGHT_BY_THE_ADVISORS

**Description:**
Set to 1 if the course is taught by the advisors who gave advice to student, otherwise, set to 0

---

## Root Cause
**Semantic confusion: SQL checks if teachers are advisors (p_id_dummy), but GT checks if teachers are advisees (p_id) - people being advised by someone**

### Incorrect SQL Logic
```sql
advised_by_data AS (
    SELECT DISTINCT
        p_id_dummy as advisor_id
    FROM {{ source('airbyte_schema', 'advisedby') }}
),

course_professors AS (
    SELECT
        tb.course_id,
        CASE WHEN ab.advisor_id IS NOT NULL THEN 1 ELSE 0 END as is_advisor
    FROM taught_by_data tb
    LEFT JOIN advised_by_data ab ON tb.p_id = ab.advisor_id
),

-- Then: MAX(is_advisor) as taught_by_the_advisors
```

### Correct SQL Logic
```sql
advised_students AS (
    SELECT DISTINCT
        p_id as advisee_id
    FROM {{ source('airbyte_schema', 'advisedby') }}
),

course_professors AS (
    SELECT
        tb.course_id,
        CASE WHEN ast.advisee_id IS NOT NULL THEN 1 ELSE 0 END as is_advisee
    FROM taught_by_data tb
    LEFT JOIN advised_students ast ON tb.p_id = ast.advisee_id
),

-- Then: MAX(is_advisee) as taught_by_the_advisors
```

---

## Why the Original Logic Is Wrong

* **What the column description means (per GT):**
  * A course is "taught by the advisors" if at least one of its teachers is a person who IS BEING ADVISED (i.e., they are an advisee in the advisedby table)
  * The phrase "advisors who gave advice to student" is confusingly worded, but the GT shows it means people who are receiving advice (students who have advisors)

* **What the SQL actually computes:**
  * The SQL checks if any teacher is in `advisedby.p_id_dummy` (people who GIVE advice)
  * This is the opposite - it finds courses taught by people who ARE advisors, not people who HAVE advisors

**Schema verification:**
- `advisedby.p_id`: "id number identifying each person" (the student being advised)
- `advisedby.p_id_dummy`: "the id number identifying the advisor" (the person giving advice)

---

## Evidence

**Key comparison demonstrating the error:**

| Course ID | Teachers | Wrong Logic (taught by advisors p_id_dummy) | Correct Logic (taught by advisees p_id) | Ground Truth |
| --------- | -------- | ------------------------------------------- | --------------------------------------- | ------------ |
| 21.0      | [22, 99] | 0                                           | 1                                       | 1            |
| 49.0      | [64, 189, 248, 263] | 0                                | 1                                       | 1            |
| 165.0     | [75, 141, 181, 231, 364] | 0                             | 1                                       | 1            |
| 2.0       | [180]    | 1                                           | 0                                       | 0            |
| 3.0       | [279]    | 1                                           | 0                                       | 0            |
| 7.0       | [415]    | 1                                           | 0                                       | 0            |

**Example demonstrating the difference:**
- Course 21.0: Taught by p_id=[22, 99]
  - p_id=99 is an advisee (appears in advisedby.p_id), advised by p_id=104
  - Wrong logic: Neither 22 nor 99 is an advisor (p_id_dummy) → 0
  - Correct logic: p_id=99 is an advisee (p_id) → 1
  - GT = 1

- Course 2.0: Taught by p_id=[180]
  - p_id=180 is an advisor (appears in advisedby.p_id_dummy), advising students
  - Wrong logic: 180 IS an advisor → 1
  - Correct logic: 180 is NOT an advisee (not in p_id) → 0
  - GT = 0

**Statistics:**
- Only 6 courses are taught by advisees (GT=1)
- 90 courses are taught by at least one advisor (wrong logic says 1)
- The two sets barely overlap

**Impact:**
* Current implementation: **42/132 matches (31.8%)**
* Corrected implementation: **132/132 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Courses where `TAUGHT_BY_THE_ADVISORS = 1`:**
- Course 21.0: Teacher p_id=99 is advised by p_id=104
- Course 38.0: Teacher p_id=204 is advised by p_id=104
- Course 49.0: Teacher p_id=263 is advised by p_id=5
- Course 51.0: Teacher p_id=18 is advised by p_id=335
- Course 124.0: Teacher p_id=9 is advised by p_id=335
- Course 165.0: Teachers p_id=75,141 are advised by p_id=331

**Key insight:**
The column description "taught by the advisors who gave advice to student" is misleading. The GT shows it actually means "taught by people who ARE BEING advised" (advisees), not "taught by people who GIVE advice" (advisors). The correct join is on `advisedby.p_id` (advisees), not `advisedby.p_id_dummy` (advisors).
