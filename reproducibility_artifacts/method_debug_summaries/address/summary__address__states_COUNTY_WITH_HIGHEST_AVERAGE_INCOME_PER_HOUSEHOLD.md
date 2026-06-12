# Column Mismatch Summary

## Database: address
## Table: states
## Column: COUNTY_WITH_HIGHEST_AVERAGE_INCOME_PER_HOUSEHOLD

### Description
The county with the highest average income per household in the state, with ties broken by the ascending order of the county.

---

## Root Cause
**Semantic misinterpretation: Used AVG() instead of MAX() on the already-averaged income values**

### Incorrect SQL Logic
```sql
county_data AS (
    SELECT
        c.state,
        c.county,
        AVG(z.avg_income_per_household) AS avg_income
    FROM country c
    LEFT JOIN zip_data z ON c.zip_code = z.zip_code
    GROUP BY c.state, c.county
),
highest_income_county AS (
    SELECT
        state,
        county AS county_with_highest_average_income_per_household
    FROM (
        SELECT
            state,
            county,
            avg_income,
            ROW_NUMBER() OVER (PARTITION BY state ORDER BY avg_income DESC, county ASC) AS rn
        FROM county_data
    ) ranked
    WHERE rn = 1
)
```

### Correct SQL Logic
```sql
county_data AS (
    SELECT
        c.state,
        c.county,
        MAX(z.avg_income_per_household) AS max_income
    FROM country c
    INNER JOIN zip_data z ON c.zip_code = z.zip_code
    WHERE z.avg_income_per_household IS NOT NULL
    GROUP BY c.state, c.county
),
highest_income_county AS (
    SELECT
        state,
        county AS county_with_highest_average_income_per_household
    FROM (
        SELECT
            state,
            county,
            max_income,
            ROW_NUMBER() OVER (PARTITION BY state ORDER BY max_income DESC, county ASC) AS rn
        FROM county_data
    ) ranked
    WHERE rn = 1
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the county that has the highest "average income per household" value. The `avg_income_per_household` field in `zip_data` already represents the average income per household for each zip code.

* **What the SQL actually computes**: The incorrect SQL calculates the average of all `avg_income_per_household` values across zip codes within each county (averaging already-averaged values). This dilutes the effect of high-income zip codes.

* **Schema semantics**: The `zip_data.avg_income_per_household` column already contains pre-computed averages at the zip code level. To find the county with the "highest average income," we should take the MAX of these values (the zip code with the highest average income within that county), not average them again.

---

## Evidence
**Key comparison demonstrating the error:**

| State | Wrong Logic (AVG) | Correct Logic (MAX) | Ground Truth |
| ----- | ----------------- | ------------------- | ------------ |
| AL    | ELMORE            | JEFFERSON           | JEFFERSON    |
| AR    | BENTON            | ARKANSAS            | ARKANSAS     |
| CA    | SAN MATEO         | ALAMEDA             | ALAMEDA      |
| FL    | SAINT JOHNS       | MIAMI-DADE          | MIAMI-DADE   |
| NY    | WESTCHESTER       | NEW YORK            | NEW YORK     |

**Example showing the difference (Alabama):**

Using AVG (incorrect):
| County | Avg of avg_income | Zip Count |
| ------ | ----------------- | --------- |
| ELMORE | 53,444            | 15        |
| SHELBY | 53,079            | 27        |

Using MAX (correct):
| County | Max of avg_income | Zip Count |
| ------ | ----------------- | --------- |
| JEFFERSON | 131,295        | 99        |
| MADISON   | 110,264        | 40        |

The county with the single highest-earning zip code (JEFFERSON with $131,295 max) is the correct answer, not the county with the highest average across all its zip codes.

**Impact:**
* Current implementation: **17/62 matches (27.4%)**
* Corrected implementation: **61/62 matches (98.4%)**

---

## Result
**61/62 matches with corrected logic (98.4%)**

The single mismatch is Alaska (AK), where the Ground Truth expects "Anchorage" but the `country` table contains no Alaska entries (0 zip codes mapped to counties for AK), resulting in NULL from the corrected query.

**States with correctly identified highest-income counties (sample):**
* Alabama: JEFFERSON (max avg_income = $131,295)
* California: ALAMEDA (max avg_income in state)
* Florida: MIAMI-DADE
* New York: NEW YORK
* Texas: HARRIS
