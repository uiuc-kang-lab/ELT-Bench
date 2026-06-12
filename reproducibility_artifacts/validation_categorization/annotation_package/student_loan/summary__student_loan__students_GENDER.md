# Column Mismatch Summary

## Database: student_loan
## Table: students
## Column: GENDER

**Description:**
The gender of the student.

---

## Root Cause
**String format mismatch - using 'Male'/'Female' instead of 'M'/'F'**

### Current SQL Logic (Incorrect)
```sql
gender_info AS (
    SELECT
        p.name,
        CASE
            WHEN m.name IS NOT NULL THEN 'Male'
            ELSE 'Female'
        END AS gender
    FROM person_base p
    LEFT JOIN male m ON p.name = m.name
)
```

### Expected Logic
```sql
gender_info AS (
    SELECT
        p.name,
        CASE
            WHEN m.name IS NOT NULL THEN 'M'
            ELSE 'F'
        END AS gender
    FROM person_base p
    LEFT JOIN male m ON p.name = m.name
)
```

---

## Why This Is Wrong

* **What the column should compute:**
  * Gender as 'M' for male, 'F' for female

* **What the SQL actually computes:**
  * Gender as 'Male' for male, 'Female' for female

* **The issue:**
  * Simple string format difference
  * GT uses abbreviated format: 'M', 'F'
  * Pred uses full words: 'Male', 'Female'

---

## Evidence

**Impact:**
* Current implementation: **0/1000 matches (0%)**

| NAME | GT | Pred |
|------|-----|------|
| student1 | M | Male |
| student10 | F | Female |
| student100 | F | Female |
| student1000 | F | Female |
| student101 | M | Male |

---

## Result

**Requires fix: Change output format from 'Male'/'Female' to 'M'/'F'**

The SQL should return 'M' instead of 'Male' and 'F' instead of 'Female'.
