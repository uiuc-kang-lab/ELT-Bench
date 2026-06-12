# Column Mismatch Summary

## Database: student_loan
## Table: schools
## Column: PER_DISABLED_FEMALE_STUDENTS

**Description:**
The percentage of disabled female students in the school.

---

## Root Cause
**Two errors: (1) Wrong denominator (total students instead of disabled students), and (2) Outputting as percentage instead of ratio**

### Incorrect SQL Logic
```sql
disabled_female AS (
    SELECT
        ss.school,
        COUNT(DISTINCT CASE WHEN d.name IS NOT NULL AND m.name IS NULL THEN ss.name END) AS num_disabled_female
    FROM school_students ss
    LEFT JOIN disabled d ON ss.name = d.name
    LEFT JOIN male m ON ss.name = m.name
    GROUP BY ss.school
)
-- Final calculation:
(df.num_disabled_female * 100.0 / ts.total_students) AS per_disabled_female_students
```

### Correct SQL Logic
```sql
disabled_female AS (
    SELECT
        ss.school,
        COUNT(DISTINCT CASE WHEN d.name IS NOT NULL AND m.name IS NULL THEN ss.name END) AS num_disabled_female,
        COUNT(DISTINCT CASE WHEN d.name IS NOT NULL THEN ss.name END) AS num_disabled
    FROM school_students ss
    LEFT JOIN disabled d ON ss.name = d.name
    LEFT JOIN male m ON ss.name = m.name
    GROUP BY ss.school
)
-- Final calculation (as ratio, not percentage):
(df.num_disabled_female * 1.0 / NULLIF(df.num_disabled, 0)) AS per_disabled_female_students
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The percentage of disabled female students in the school"
  * This means: among disabled students, what fraction are female
  * Output is a ratio (0-1), not a percentage (0-100)
  * Denominator should be: disabled students in the school

* **What the SQL actually computes:**
  * (disabled female students) / (all students in school) * 100
  * This calculates: what percentage of all students are disabled AND female
  * Wrong denominator AND wrong scale (percentage instead of ratio)

---

## Evidence

**Key comparison demonstrating the error:**

| School | Disabled Female | Disabled Total | Total Students | Wrong Formula | Correct Formula | Ground Truth |
| ------ | --------------- | -------------- | -------------- | ------------- | --------------- | ------------ |
| occ    | 14              | 24             | 247            | 5.67%         | 0.5833          | 0.5833       |
| smc    | 1               | 17             | 226            | 0.44%         | 0.0588          | 0.0588       |
| ucb    | 3               | 8              | 89             | 3.37%         | 0.3750          | 0.3750       |
| uci    | 12              | 20             | 230            | 5.22%         | 0.6000          | 0.6000       |
| ucla   | 18              | 28             | 236            | 7.63%         | 0.6429          | 0.6429       |
| ucsd   | 5               | 17             | 166            | 3.01%         | 0.2941          | 0.2941       |

**Formula verification:**
- occ: Wrong = 14/247 * 100 = 5.67%, Correct = 14/24 = 0.5833
- uci: Wrong = 12/230 * 100 = 5.22%, Correct = 12/20 = 0.6000

**Impact:**
* Current implementation: **0/6 matches (0%)**
* Corrected implementation: **6/6 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The ground truth stores this as a ratio (0-1) rather than a percentage (0-100). The phrase "percentage of disabled female students" means "among disabled students, what fraction are female" - and the output is stored as a decimal ratio.
