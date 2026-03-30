# Column Mismatch Summary

## Database: cs_semester
## Table: students
## Column: GPA_BASED_ON_REGISTRATION

**Description:**
The GPA of the student based on the courses the student registered

---

## Root Cause
**NULL grade handling error: SQL treats NULL grades as 0 grade points, but GT treats NULL grades as D (1.0 grade points)**

### Incorrect SQL Logic
```sql
gpa_calculation AS (
    SELECT
        r.student_id,
        SUM(CASE
            WHEN r.grade = 'A' THEN 4.0 * c.credit
            WHEN r.grade = 'B' THEN 3.0 * c.credit
            WHEN r.grade = 'C' THEN 2.0 * c.credit
            WHEN r.grade = 'D' THEN 1.0 * c.credit
            ELSE 0  -- NULL grades treated as 0
        END) / NULLIF(SUM(c.credit), 0) AS GPA_based_on_registration
    FROM registration_data r
    JOIN course_data c ON r.course_id = c.course_id
    GROUP BY r.student_id
)
```

### Correct SQL Logic
```sql
gpa_calculation AS (
    SELECT
        r.student_id,
        SUM(CASE
            WHEN r.grade = 'A' THEN 4.0 * c.credit
            WHEN r.grade = 'B' THEN 3.0 * c.credit
            WHEN r.grade = 'C' THEN 2.0 * c.credit
            WHEN r.grade = 'D' THEN 1.0 * c.credit
            WHEN r.grade IS NULL THEN 1.0 * c.credit  -- NULL treated as D
            ELSE 0  -- F or unknown
        END) / NULLIF(SUM(c.credit), 0) AS GPA_based_on_registration
    FROM registration_data r
    JOIN course_data c ON r.course_id = c.course_id
    GROUP BY r.student_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * GPA is calculated based on all registered courses
  * NULL grades represent incomplete or pending grades
  * In this dataset, NULL grades are treated as D (1.0 points) for GPA calculation purposes

* **What the SQL actually computes:**
  * The ELSE clause in the CASE statement defaults NULL grades to 0 points
  * Credits from courses with NULL grades are still counted in the denominator
  * This results in lower GPA than intended

**Schema verification:**
- `registration.grade`: "the grades that the students acquire in this course"
- `registration.course_id`: "the id of courses"
- `course.credit`: "credit of the course"

**Grade distribution in registration table:**
- A: 37 records
- B: 28 records
- C: 22 records
- D: 9 records
- NULL: 5 records (no F grades exist)

---

## Evidence

**Key comparison demonstrating the error:**

| Student | Courses & Grades | Credits | Points (NULL=0) | Points (NULL=D) | GPA (NULL=0) | GPA (NULL=D) | GT |
| ------- | ---------------- | ------- | --------------- | --------------- | ------------ | ------------ | -- |
| 11 | A(3cr), null(2cr), B(2cr), C(3cr) | 10 | 24 | 26 | 2.4 | 2.6 | 2.6 |
| 17 | C(2cr), B(2cr), D(2cr), null(3cr) | 9 | 12 | 15 | 1.33 | 1.67 | 1.67 |
| 23 | B(2cr), null(3cr), B(2cr), A(2cr), B(2cr), C(3cr) | 14 | 32 | 35 | 2.29 | 2.5 | 2.5 |
| 33 | D(2cr), A(3cr), null(3cr) | 8 | 14 | 17 | 1.75 | 2.125 | 2.125 |
| 36 | null(2cr), C(2cr) | 4 | 4 | 6 | 1.0 | 1.5 | 1.5 |

**Example calculation for Student 11:**
- Registrations:
  - Course 8 (3 credits): Grade A = 4.0 * 3 = 12 points
  - Course 10 (2 credits): Grade NULL = 1.0 * 2 = 2 points (as D)
  - Course 11 (2 credits): Grade B = 3.0 * 2 = 6 points
  - Course 12 (3 credits): Grade C = 2.0 * 3 = 6 points
- Total: 26 points / 10 credits = 2.6 GPA (matches GT)
- Wrong calculation: 24 points / 10 credits = 2.4 GPA (NULL=0)

**Impact:**
* Current implementation: **33/38 matches (86.8%)**
* Corrected implementation: **38/38 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
In this academic database, NULL grades in the registration table represent incomplete or pending grades that are treated as D (1.0 grade points) for GPA calculation purposes. The SQL must explicitly handle NULL values with `WHEN r.grade IS NULL THEN 1.0 * c.credit` rather than letting them fall through to the ELSE clause which assigns 0 points.

**Students affected by this issue:**
- Student 11: has NULL grade in Data Structure and Algorithms
- Student 17: has NULL grade in Applied Deep Learning
- Student 23: has NULL grade in Computer Vision
- Student 33: has NULL grade in Statistical learning
- Student 36: has NULL grade in Intro to Database 2
