# Column Mismatch Summary

## Database: address
## Table: states
## Column: HIGHER_AVG_FEMALE_PER

### Description
Set to 1 if the state's percentage of female population is higher than the average percentage of female population across all states, otherwise, set to 0.

---

## Root Cause
**Two errors: (1) Wrong population denominator and (2) Incorrect average calculation including zero-population states**

### Incorrect SQL Logic
```sql
zip_data_aggregated AS (
    SELECT
        state,
        SUM(COALESCE(female_population, 0)) AS total_female,
        SUM(COALESCE(population_2020, 0)) AS total_population
    FROM zip_data
    GROUP BY state
),
avg_female_percentage AS (
    SELECT
        AVG(CASE
            WHEN total_population > 0
            THEN (total_female * 100.0 / total_population)
            ELSE 0
        END) AS avg_female_pct
    FROM zip_data_aggregated
)
-- Final SELECT uses:
CASE
    WHEN z.total_population > 0 AND (z.total_female * 100.0 / z.total_population) > avg_female_pct
    THEN 1
    ELSE 0
END AS higher_avg_female_per
```

### Correct SQL Logic
```sql
zip_data_aggregated AS (
    SELECT
        state,
        SUM(COALESCE(female_population, 0)) AS total_female,
        SUM(COALESCE(male_population, 0)) AS total_male,
        SUM(COALESCE(male_population, 0)) + SUM(COALESCE(female_population, 0)) AS total_gendered_pop
    FROM zip_data
    GROUP BY state
    HAVING total_gendered_pop > 0
),
state_female_pct AS (
    SELECT
        state,
        total_female * 100.0 / total_gendered_pop AS female_pct
    FROM zip_data_aggregated
),
avg_female_percentage AS (
    SELECT AVG(female_pct) AS avg_female_pct
    FROM state_female_pct
)
-- Final SELECT uses:
CASE
    WHEN s.female_pct > (SELECT avg_female_pct FROM avg_female_percentage)
    THEN 1
    ELSE 0
END AS higher_avg_female_per
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Calculate each state's female percentage, compute the average of these percentages across all states with data, then flag states above this average.

* **Error 1 - Wrong denominator**: The original SQL uses `population_2020` as the denominator, but this total population figure doesn't align with `male_population + female_population`. The correct approach is to use `(male_population + female_population)` as the denominator to calculate gender ratios.

* **Error 2 - Including zero-population entries**: The `ELSE 0` clause in the AVG calculation incorrectly includes zero-population states/territories (AA, AE, AP, AS, FM, GU, MH, MP, PW, VI) as having 0% female population, which dramatically skews the average downward.

* **Result of errors**: The incorrect average (~41.59%) is much lower than the correct average (~50.74%), causing almost all states to appear "above average."

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Wrong Logic | Correct Logic |
| ------ | ----------- | ------------- |
| Average female % | 41.59% | 50.74% |
| States flagged as 1 | 52 | 28 |

**Boundary analysis:**
| State | Female % | GT Value |
| ----- | -------- | -------- |
| VT (Vermont) | 50.745% | 1 (lowest GT=1) |
| WV (West Virginia) | 50.697% | 0 (highest GT=0) |

The threshold is the average of state percentages = **50.736517%**, which falls exactly between VT and WV.

**Example of miscategorized states:**
| State | Female % (correct calc) | Wrong Pred | Correct Pred | GT |
| ----- | ----------------------- | ---------- | ------------ | -- |
| WV    | 50.70%                  | 1          | 0            | 0  |
| NH    | 50.67%                  | 1          | 0            | 0  |
| AK    | 48.47%                  | 1          | 0            | 0  |
| WY    | 49.00%                  | 1          | 0            | 0  |

**Impact:**
* Current implementation: **38/62 matches (61.3%)**
* Corrected implementation: **62/62 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**States where `HIGHER_AVG_FEMALE_PER = 1` (female % > 50.74%):**
* DC (52.79%), PR (52.10%), RI (51.70%), MD (51.65%), MA (51.64%)
* NY (51.61%), DE (51.56%), AL (51.46%), MS (51.43%), SC (51.35%)
* CT (51.33%), NJ (51.32%), NC (51.28%), PA (51.27%), TN (51.26%)
* GA (51.18%), OH (51.18%), FL (51.12%), ME (51.06%), LA (51.05%)
* MO (51.02%), IL (50.96%), MI (50.95%), VA (50.93%), AR (50.90%)
* IN (50.80%), KY (50.79%), VT (50.75%)
