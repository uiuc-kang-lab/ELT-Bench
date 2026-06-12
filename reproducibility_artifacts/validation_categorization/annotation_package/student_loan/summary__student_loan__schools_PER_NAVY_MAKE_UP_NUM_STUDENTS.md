# Column Mismatch Summary

## Database: student_loan
## Table: schools
## Column: PER_NAVY_MAKE_UP_NUM_STUDENTS

**Description:**
The percentage of students who enlisted in the navy make up the number of students enrolled in the school.

---

## Root Cause
**Wrong denominator: Using total school students instead of total navy enrollments across all schools**

### Incorrect SQL Logic
```sql
navy_count AS (
    SELECT
        ss.school,
        COUNT(DISTINCT CASE WHEN e.organ = 'navy' THEN ss.name END) AS num_navy
    FROM school_students ss
    LEFT JOIN enlist e ON ss.name = e.name
    GROUP BY ss.school
)
-- Final calculation:
(nc.num_navy * 100.0 / ts.total_students) AS per_navy_make_up_num_students
```

### Correct SQL Logic
```sql
-- First, get total navy enrollments across all schools
total_navy AS (
    SELECT COUNT(*) AS total_navy_enrollments
    FROM enrolled e
    INNER JOIN enlist en ON e.name = en.name
    WHERE en.organ = 'navy'
),
navy_count AS (
    SELECT
        ss.school,
        COUNT(CASE WHEN e.organ = 'navy' THEN 1 END) AS num_navy
    FROM school_students ss
    LEFT JOIN enlist e ON ss.name = e.name
    GROUP BY ss.school
)
-- Final calculation:
(nc.num_navy * 100.0 / tn.total_navy_enrollments) AS per_navy_make_up_num_students
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The percentage of students who enlisted in the navy make up the number of students enrolled in the school"
  * This awkward phrasing means: what percentage of all navy enrollments are from this school
  * Denominator should be: total navy enrollments across all schools (45)

* **What the SQL actually computes:**
  * (navy students in school) / (all students in school) * 100
  * This calculates: what percentage of the school's students are in the navy
  * Wrong denominator: school total instead of total navy enrollments

* **Key data insight:**
  * There are 37 unique navy students
  * These 37 students appear in 45 school enrollments (some students enrolled in multiple schools)
  * The formula uses 45 as the denominator

---

## Evidence

**Key comparison demonstrating the error:**

| School | Navy in School | Total Students | Total Navy Enrollments | Wrong Formula | Correct Formula | Ground Truth |
| ------ | -------------- | -------------- | ---------------------- | ------------- | --------------- | ------------ |
| occ    | 8              | 247            | 45                     | 3.24%         | 17.78%          | 17.78%       |
| smc    | 9              | 226            | 45                     | 3.98%         | 20.00%          | 20.00%       |
| ucb    | 2              | 89             | 45                     | 2.25%         | 4.44%           | 4.44%        |
| uci    | 10             | 230            | 45                     | 4.35%         | 22.22%          | 22.22%       |
| ucla   | 7              | 236            | 45                     | 2.97%         | 15.56%          | 15.56%       |
| ucsd   | 9              | 166            | 45                     | 5.42%         | 20.00%          | 20.00%       |

**Formula verification:**
- occ: Wrong = 8/247 = 3.24%, Correct = 8/45 = 17.78%
- uci: Wrong = 10/230 = 4.35%, Correct = 10/45 = 22.22%

**Navy enrollment breakdown:**
- 37 unique navy students enrolled across 6 schools
- Total enrollments: 8+9+2+10+7+9 = 45 (some students in multiple schools)

**Impact:**
* Current implementation: **0/6 matches (0%)**
* Corrected implementation: **6/6 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The column represents the school's share of all navy enrollments. The denominator is the total count of navy students across all schools (45), not the total students in that specific school. This answers "what percentage of navy students are enrolled in this school?" rather than "what percentage of this school's students are navy?"
