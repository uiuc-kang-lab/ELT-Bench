# Column Mismatch Summary

## Database: college_completion
## Table: states
## Column: INSTITUTE_WITH_MOST_NUMBER_OF_AMERICAN_INDIAN

**Description:**
Institution with most number of American Indian students in the state, with ties broken by the ascending order of the institute name

---

## Root Cause
**GT-SQL semantic mismatch: SQL correctly implements the column description (institution with highest American Indian student count), but GT appears to use different logic - possibly selecting institutions with zero American Indian data**

### Current SQL Logic (Correct per description)
```sql
american_indian_by_institute AS (
    SELECT
        d.STATE,
        d.CHRONNAME,
        SUM(g.GRAD_COHORT) as total_american_indian
    FROM institution_details d
    JOIN institution_grads g ON d.UNITID = g.UNITID
    WHERE g.RACE = 'Ai' AND g.GRAD_COHORT IS NOT NULL
    GROUP BY d.STATE, d.CHRONNAME
),

most_american_indian AS (
    SELECT
        STATE,
        CHRONNAME as institute_with_most_number_of_American_Indian
    FROM (
        SELECT
            STATE,
            CHRONNAME,
            total_american_indian,
            ROW_NUMBER() OVER (PARTITION BY STATE ORDER BY total_american_indian DESC, CHRONNAME ASC) as rn
        FROM american_indian_by_institute
    )
    WHERE rn = 1
)
```

### GT Logic (Inferred)
The GT appears to select institutions that have **zero or no American Indian student data**, not the institution with the most American Indian students.

---

## Why the SQL May Be Correct (But GT Is Different)

* The SQL correctly implements the column description:
  * Joins `institution_details` with `institution_grads` where `RACE = 'Ai'`
  * Sums `GRAD_COHORT` per institution per state
  * Selects institution with highest sum, ties broken alphabetically

* However, the GT values:
  * Often have **zero** American Indian GRAD_COHORT sum
  * Do not correspond to institutions with the highest count
  * May represent a different business logic or data source

**Schema verification:**
- `institution_grads.race`: "race/ethnicity of students" - value 'Ai' represents American Indian
- `institution_grads.grad_cohort`: "Number of first-time, full-time, degree-seeking students in the cohort"

---

## Evidence

**Key comparison demonstrating the discrepancy:**

| State | GT Institution | GT AI Count | Correct Institution | Correct AI Count |
| ----- | -------------- | ----------- | ------------------- | ---------------- |
| Alabama | ITT Technical Institute-Madison | 0 | Calhoun Community College | 864 |
| Arizona | Argosy University-Phoenix | 0 | Carrington College at Phoenix | 5,278 |
| California | Argosy University-Inland Empire | 0 | WyoTech at Long Beach | 1,332 |
| Colorado | ITT Technical Institute-Aurora | 0 | Fort Lewis College | 3,728 |
| Kansas | Barton County Community College | 192 | Haskell Indian Nations University | 5,618 |

**Impact:**
* Current implementation (MAX AI count): **19/51 matches (37.3%)**
* First institution with NO AI data: **12/51 matches (23.5%)**

---

## Result

**Unable to match GT logic**

The SQL correctly implements the column description ("institution with most number of American Indian students"), but the GT values do not correspond to this logic. The GT institutions typically have zero American Indian students in the data.

**Possible explanations:**
1. The GT was generated using a different data source
2. The column description doesn't accurately reflect the GT calculation
3. There may be additional filtering criteria not captured in the description

**Recommendation:**
- The SQL implementation is correct per the column description
- The GT should be reviewed for accuracy
- Alternatively, the column description should be updated to reflect actual GT logic
