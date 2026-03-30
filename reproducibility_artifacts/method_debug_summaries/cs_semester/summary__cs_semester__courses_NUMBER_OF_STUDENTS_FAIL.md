# Column Mismatch Summary

## Database: cs_semester
## Table: courses
## Column: NUMBER_OF_STUDENTS_FAIL

**Description:**
The number of students who fail the course, replace NULL values with 0

---

## Root Cause
**NULL grade handling error: SQL counts only grade='F', but GT treats NULL grades as fail (and no F grades exist in the data)**

### Incorrect SQL Logic
```sql
students_failed AS (
    SELECT
        course_id,
        COUNT(*) AS number_of_students_fail
    FROM registration_data
    WHERE grade = 'F'
    GROUP BY course_id
)
```

### Correct SQL Logic
```sql
students_failed AS (
    SELECT
        course_id,
        COUNT(*) AS number_of_students_fail
    FROM registration_data
    WHERE grade IS NULL OR grade = 'F'
    GROUP BY course_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count students who failed each course
  * In this dataset, NULL grades represent incomplete/failing grades
  * A NULL grade should be counted as a fail

* **What the SQL actually computes:**
  * Only counts registrations where grade = 'F'
  * Since there are NO 'F' grades in the registration table, this returns 0 for all courses
  * NULL grades are completely ignored

**Schema verification:**
- `registration.grade`: "the grades that the students acquire in this course"
- `registration.course_id`: "the id of courses"
- `registration.student_id`: "the id of students"

**Grade distribution in registration table:**
- A: 37 records
- B: 28 records
- C: 22 records
- D: 9 records
- NULL: 5 records
- F: 0 records (no F grades exist!)

---

## Evidence

**Key comparison demonstrating the error:**

| Course ID | Course Name | Students with NULL Grade | Wrong Logic (grade='F') | Correct Logic (NULL or F) | GT |
| --------- | ----------- | ------------------------ | ----------------------- | ------------------------- | -- |
| 3 | Statistical learning | 1 (student 33) | 0 | 1 | 1 |
| 7 | Computer Vision | 1 (student 23) | 0 | 1 | 1 |
| 10 | Data Structure and Algorithms | 1 (student 11) | 0 | 1 | 1 |
| 12 | Applied Deep Learning | 1 (student 17) | 0 | 1 | 1 |
| 13 | Intro to Database 2 | 1 (student 36) | 0 | 1 | 1 |
| 1 | Machine Learning | 0 | 0 | 0 | 0 |
| 2 | Natural Language Processing | 0 | 0 | 0 | 0 |

**Example demonstrating the difference:**
- Course 3 (Statistical learning):
  - Student 33 has grade = NULL
  - Wrong logic: grade = 'F' matches 0 students -> 0
  - Correct logic: grade IS NULL matches 1 student -> 1
  - GT = 1

**Students with NULL grades (counted as fail):**
- Course 3: Student 33 (NULL grade)
- Course 7: Student 23 (NULL grade)
- Course 10: Student 11 (NULL grade)
- Course 12: Student 17 (NULL grade)
- Course 13: Student 36 (NULL grade)

**Impact:**
* Current implementation: **8/13 matches (61.5%)**
* Corrected implementation: **13/13 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that in this academic database:
1. There are NO 'F' grades in the registration table
2. NULL grades represent incomplete or failing grades
3. The ground truth treats NULL grades as failures

The SQL must check for `grade IS NULL OR grade = 'F'` to properly count all failing students. With only `grade = 'F'`, the query returns 0 for all courses since no F grades exist.

**Courses with students who failed (NULL grades):**
- Course 3 (Statistical learning): 1 fail
- Course 7 (Computer Vision): 1 fail
- Course 10 (Data Structure and Algorithms): 1 fail
- Course 12 (Applied Deep Learning): 1 fail
- Course 13 (Intro to Database 2): 1 fail
