# Column Mismatch Summary

## Database: california_schools
## Table: ca__schools
## Column: PERCENT_ELIGIBLE_FREE_MEALS_FOR_AGES_5_17

### Description
The percentage of eligible free meals for ages 5 to 17 of the school

---

## Root Cause
**Data format mismatch: Source stores decimal ratios (0-1) but column expects percentages (0-100)**

### Incorrect SQL Logic
```sql
frpm AS (
    SELECT
        CDSCode,
        percent___eligible_free_ages_5_17 AS percent_eligible_free_meals_for_ages_5_17,
        ...
    FROM {{ source('airbyte_schema', 'frpm') }}
)
```

### Correct SQL Logic
```sql
frpm AS (
    SELECT
        CDSCode,
        Percent___Eligible_Free_Ages_5_17 * 100 AS percent_eligible_free_meals_for_ages_5_17,
        ...
    FROM {{ source('airbyte_schema', 'frpm') }}
)
```

---

## Why the Original Logic Is Wrong

* The source column `Percent___Eligible_Free_Ages_5_17` in the FRPM table stores percentage values as decimal ratios (0.0 to 1.0), where 0.52 represents 52%
* The column description states "The percentage of eligible free meals" which implies values in the range 0-100
* The SQL directly maps the source value without converting from ratio to percentage format
* This results in values that are 100x smaller than expected (e.g., 0.52 instead of 52)

---

## Evidence

**Key comparison demonstrating the error:**

| School CDSCode    | Source Value | Wrong Logic | Correct Logic | Ground Truth |
| ----------------- | ------------ | ----------- | ------------- | ------------ |
| 1100170109835     | 0.516822     | 0.52        | 51.68         | 51.68        |
| 1100170112607     | 0.484043     | 0.48        | 48.40         | 48.40        |
| 1100170118489     | 0.556522     | 0.56        | 55.65         | 55.65        |
| 1100170123968     | 0.594737     | 0.59        | 59.47         | 59.47        |
| 1100170124172     | 0.054475     | 0.05        | 5.45          | 5.45         |

**Data format verification from source:**
```
Sample FRPM records showing calculation:
CDSCode         Enrollment_Ages_5_17  Free_Meal_Count_Ages_5_17  Percent___Eligible_Free_Ages_5_17
1100170109835   1070                  553                        0.516822
1100170112607   376                   182                        0.484043
```

The source `Percent___Eligible_Free_Ages_5_17` = Free_Meal_Count_Ages_5_17 / Enrollment_Ages_5_17, stored as a decimal.

**Impact:**
* Current implementation: **7,778/17,686 matches (44.0%)**
* Corrected implementation: **17,686/17,686 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The FRPM (Free or Reduced Price Meals) data stores percentage values as decimal ratios where 1.0 = 100%. The SQL must multiply by 100 to convert to actual percentage values that match the column's semantic meaning of "percentage of eligible free meals."
