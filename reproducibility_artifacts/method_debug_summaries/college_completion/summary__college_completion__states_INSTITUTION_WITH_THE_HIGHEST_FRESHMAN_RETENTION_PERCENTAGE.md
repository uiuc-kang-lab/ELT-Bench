# Column Mismatch Summary

## Database: college_completion
## Table: states
## Column: INSTITUTION_WITH_THE_HIGHEST_FRESHMAN_RETENTION_PERCENTAGE

**Description:**
Institution with the highest freshman retention percentage in the state, with ties broken by the ascending order of the institute name

---

## Root Cause
**GT-SQL semantic inversion: SQL correctly implements MAX(RETAIN_VALUE), but GT selects institutions where RETAIN_VALUE IS NULL (first alphabetically)**

### Current SQL Logic (Correct per description)
```sql
highest_retention AS (
    SELECT
        STATE,
        CHRONNAME as institution_with_the_highest_freshman_retention_percentage
    FROM (
        SELECT
            STATE,
            CHRONNAME,
            RETAIN_VALUE,
            ROW_NUMBER() OVER (PARTITION BY STATE ORDER BY RETAIN_VALUE DESC, CHRONNAME ASC) as rn
        FROM institution_details
        WHERE RETAIN_VALUE IS NOT NULL
    )
    WHERE rn = 1
)
```

### GT Logic (Inferred)
```sql
highest_retention AS (
    SELECT
        STATE,
        CHRONNAME as institution_with_the_highest_freshman_retention_percentage
    FROM (
        SELECT
            STATE,
            CHRONNAME,
            ROW_NUMBER() OVER (PARTITION BY STATE ORDER BY CHRONNAME ASC) as rn
        FROM institution_details
        WHERE RETAIN_VALUE IS NULL
    )
    WHERE rn = 1
)
-- For states with no NULL RETAIN_VALUE institutions, use MAX(RETAIN_VALUE)
```

---

## Why the SQL Implements Description But GT Is Different

* The column description says "highest freshman retention percentage"
* The SQL correctly:
  * Filters for `RETAIN_VALUE IS NOT NULL`
  * Orders by `RETAIN_VALUE DESC`
  * Breaks ties alphabetically (ASC)

* However, the GT:
  * Selects institutions where `RETAIN_VALUE IS NULL`
  * Orders alphabetically (first name wins)
  * For states without NULL RETAIN institutions, logic is unclear

**Schema verification:**
- `institution_details.retain_value`: "share of freshman students retained for a second year"
- NULL means retention data is not available for that institution

---

## Evidence

**Key comparison demonstrating the discrepancy:**

| State | GT Institution | GT RETAIN_VALUE | Correct Institution | Correct RETAIN_VALUE |
| ----- | -------------- | --------------- | ------------------- | -------------------- |
| Alabama | ITT Technical Institute-Madison | NULL | Strayer University-Alabama | 100.0 |
| Arizona | Brookline College at Tuscon | NULL | Anthem College at Phoenix | 87.5 |
| Arkansas | ITT Technical Institute at Little Rock | NULL | Hendrix College | 87.8 |
| California | Brandman University | NULL | Charles Drew University | 100.0 |
| Florida | Allied Health Institute | NULL | Carlos Albizu University | 100.0 |

**States without NULL RETAIN institutions (hybrid logic):**
| State | GT Institution | GT RETAIN_VALUE | Max RETAIN Institution | Max RETAIN_VALUE |
| ----- | -------------- | --------------- | ---------------------- | ---------------- |
| Alaska | University of Alaska at Fairbanks | 76.9 | University of Alaska at Fairbanks | 76.9 |
| Connecticut | Yale University | 98.7 | Yale University | 98.7 |
| Maine | Bowdoin College | 96.5 | Central Maine Medical Center... | 100.0 |

**Impact:**
* Current implementation (MAX RETAIN_VALUE): **7/51 matches (13.7%)**
* First NULL RETAIN_VALUE institution: **40/51 matches (78.4%)**
* Hybrid logic (NULL first, then MAX): **47/51 matches (92.2%)**

---

## Result

**Partial match with inferred GT logic (92.2%)**

The GT appears to use inverted logic:
1. If a state has institutions with NULL RETAIN_VALUE, select the first alphabetically among those
2. If no NULL RETAIN institutions, use different criteria (unclear pattern for remaining 4 states)

**Remaining 4 mismatches (Maine, New Hampshire, Pennsylvania, Wyoming):**
- These states have no NULL RETAIN institutions
- GT doesn't pick MAX RETAIN_VALUE
- Pattern for these cases is unclear

**Key insight:**
The column description says "highest freshman retention" but the GT actually prioritizes institutions **without** retention data (NULL values). This is the opposite of what the description states.

**Recommendation:**
- The SQL implementation correctly follows the column description
- The GT logic appears to be inverted or using a different definition
- Either update the column description to match actual GT logic, or correct the GT values
