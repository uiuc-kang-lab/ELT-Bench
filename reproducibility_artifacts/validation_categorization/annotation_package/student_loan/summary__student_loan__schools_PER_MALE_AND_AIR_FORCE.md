# Column Mismatch Summary

## Database: student_loan
## Table: schools
## Column: PER_MALE_AND_AIR_FORCE

**Description:**
The percentage of male students in the air force department among the students enrolled in the school.

---

## Root Cause
**Wrong denominator: Using total students instead of air force students**

### Incorrect SQL Logic
```sql
male_air_force AS (
    SELECT
        ss.school,
        COUNT(DISTINCT CASE WHEN m.name IS NOT NULL AND e.organ = 'air_force' THEN ss.name END) AS num_male_air_force
    FROM school_students ss
    LEFT JOIN male m ON ss.name = m.name
    LEFT JOIN enlist e ON ss.name = e.name
    GROUP BY ss.school
)
-- Final calculation:
(maf.num_male_air_force * 100.0 / ts.total_students) AS per_male_and_air_force
```

### Correct SQL Logic
```sql
male_air_force AS (
    SELECT
        ss.school,
        COUNT(DISTINCT CASE WHEN m.name IS NOT NULL AND e.organ = 'air_force' THEN ss.name END) AS num_male_air_force,
        COUNT(DISTINCT CASE WHEN e.organ = 'air_force' THEN ss.name END) AS num_air_force
    FROM school_students ss
    LEFT JOIN male m ON ss.name = m.name
    LEFT JOIN enlist e ON ss.name = e.name
    GROUP BY ss.school
)
-- Final calculation:
(maf.num_male_air_force * 100.0 / NULLIF(maf.num_air_force, 0)) AS per_male_and_air_force
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The percentage of male students in the air force department"
  * This means: among students in the air force department, what percentage are male
  * Denominator should be: air force students in the school

* **What the SQL actually computes:**
  * (male AND air force students) / (all students in school) * 100
  * This calculates: what percentage of all students are both male AND in air force
  * Wrong denominator: total students instead of air force students

---

## Evidence

**Key comparison demonstrating the error:**

| School | Male Air Force | Air Force Total | Total Students | Wrong Formula | Correct Formula | Ground Truth |
| ------ | -------------- | --------------- | -------------- | ------------- | --------------- | ------------ |
| occ    | 6              | 13              | 247            | 2.43%         | 46.15%          | 46.15%       |
| uci    | 1              | 3               | 230            | 0.43%         | 33.33%          | 33.33%       |
| ucla   | 1              | 7               | 236            | 0.42%         | 14.29%          | 14.29%       |
| ucsd   | 2              | 7               | 166            | 1.20%         | 28.57%          | 28.57%       |
| smc    | 0              | 2               | 226            | 0.00%         | 0.00%           | 0.00%        |
| ucb    | 0              | 2               | 89             | 0.00%         | 0.00%           | 0.00%        |

**Formula verification:**
- occ: Wrong = 6/247 = 2.43%, Correct = 6/13 = 46.15%
- uci: Wrong = 1/230 = 0.43%, Correct = 1/3 = 33.33%

**Impact:**
* Current implementation: **2/6 matches (33.3%)** (only matches when numerator is 0)
* Corrected implementation: **6/6 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The phrase "percentage of male students in the air force department" means "among air force students, what percentage are male" - not "what percentage of all students are male and in air force."
