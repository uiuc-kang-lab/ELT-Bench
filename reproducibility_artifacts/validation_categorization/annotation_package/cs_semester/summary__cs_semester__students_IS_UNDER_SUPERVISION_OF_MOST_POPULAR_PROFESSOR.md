# Column Mismatch Summary

## Database: cs_semester
## Table: students
## Column: IS_UNDER_SUPERVISION_OF_MOST_POPULAR_PROFESSOR

**Description:**
Set to 1 if the student is under the supervision of the most popular professor, otherwise, set to 0

---

## Root Cause
**Aggregation error: SQL uses LIMIT 1 to select a single most popular professor, but multiple professors share the maximum popularity value**

### Incorrect SQL Logic
```sql
most_popular_prof AS (
    SELECT prof_id
    FROM prof_data
    ORDER BY popularity DESC
    LIMIT 1
),

under_most_popular_prof AS (
    SELECT DISTINCT
        ra.student_id,
        CASE
            WHEN ra.prof_id = (SELECT prof_id FROM most_popular_prof) THEN 1
            ELSE 0
        END AS is_under_supervision_of_most_popular_professor
    FROM ra_data ra
)
```

### Correct SQL Logic
```sql
most_popular_profs AS (
    SELECT prof_id
    FROM prof_data
    WHERE popularity = (SELECT MAX(popularity) FROM prof_data)
),

under_most_popular_prof AS (
    SELECT DISTINCT
        ra.student_id,
        CASE
            WHEN ra.prof_id IN (SELECT prof_id FROM most_popular_profs) THEN 1
            ELSE 0
        END AS is_under_supervision_of_most_popular_professor
    FROM ra_data ra
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Most popular professor" = professor(s) with the highest popularity value
  * When multiple professors share the maximum popularity, students under ANY of them should be flagged
  * The description says "the most popular professor" but this should be interpreted as all professors tied for the highest popularity

* **What the SQL actually computes:**
  * `ORDER BY popularity DESC LIMIT 1` arbitrarily selects ONE professor
  * This ignores other professors with the same maximum popularity
  * Only students under that single professor get flagged

**Schema verification:**
- `prof.popularity`: "popularity of the professor"
- `RA.prof_id`: "professor who advises this student"
- `RA.student_id`: "the id number representing each student"

**Popularity distribution:**
- 5 professors have popularity = 3 (maximum): prof_ids 1, 4, 5, 6, 8
- 5 professors have popularity = 2

---

## Evidence

**Key comparison demonstrating the error:**

| Student ID | Supervising Prof(s) | Max Pop Prof? | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ------------------- | ------------- | ----------- | ------------- | ------------ |
| 11         | 5                   | Yes (pop=3)   | 0           | 1             | 1            |
| 12         | 4                   | Yes (pop=3)   | 0           | 1             | 1            |
| 13         | 1                   | Yes (pop=3)   | 1           | 1             | 1            |
| 16         | 11, 3, 5            | Yes (5)       | 0           | 1             | 1            |
| 23         | 6, 11, 4            | Yes (6, 4)    | 0           | 1             | 1            |
| 24         | 8, 10               | Yes (8)       | 0           | 1             | 1            |
| 31         | 6, 5, 2, 3          | Yes (6, 5)    | 0           | 1             | 1            |
| 33         | 8                   | Yes (pop=3)   | 0           | 1             | 1            |
| 36         | 6, 5, 3             | Yes (6, 5)    | 0           | 1             | 1            |

**Example demonstrating the difference:**
- SQL with LIMIT 1 picks prof_id=1 (first professor with popularity=3)
- Only student 13 is supervised by prof_id=1
- But students 11, 12, 16, 23, 24, 31, 33, 36 are supervised by OTHER professors with popularity=3 (profs 4, 5, 6, 8)
- These students are incorrectly excluded

**Impact:**
* Current implementation: **30/38 matches (78.9%)**
* Corrected implementation: **38/38 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Students under supervision of most popular professors (popularity=3):**
- Student 11: supervised by prof 5
- Student 12: supervised by prof 4
- Student 13: supervised by prof 1
- Student 16: supervised by profs 3, 5, 11 (5 has pop=3)
- Student 23: supervised by profs 4, 6, 11 (4, 6 have pop=3)
- Student 24: supervised by profs 8, 10 (8 has pop=3)
- Student 31: supervised by profs 2, 3, 5, 6 (5, 6 have pop=3)
- Student 33: supervised by prof 8
- Student 36: supervised by profs 3, 5, 6 (5, 6 have pop=3)
