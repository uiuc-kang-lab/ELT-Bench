# Column Mismatch Summary

## Database: california_schools
## Table: ca__schools
## Column: PERCENT_ELIGIBLE_FREE_MEALS_FOR_GRADES_1_THROUGH_12

### Description
The percentage of eligible free meals for grades 1 through 12 of the school

---

## Root Cause
**Data format mismatch: Source stores decimal ratios (0-1) but column expects percentages (0-100)**

### Incorrect SQL Logic
```sql
frpm AS (
    SELECT
        CDSCode,
        Percent___Eligible_Free_K_12 AS percent_eligible_free_meals_for_grades_1_through_12,
        ...
    FROM {{ source('airbyte_schema', 'frpm') }}
)
```

### Correct SQL Logic
```sql
frpm AS (
    SELECT
        CDSCode,
        Percent___Eligible_Free_K_12 * 100 AS percent_eligible_free_meals_for_grades_1_through_12,
        ...
    FROM {{ source('airbyte_schema', 'frpm') }}
)
```

---

## Why the Original Logic Is Wrong

* The source column `Percent___Eligible_Free_K_12` in the FRPM table stores percentage values as decimal ratios (0.0 to 1.0), where 0.52 represents 52%
* The column description states "The percentage of eligible free meals" which implies values in the range 0-100
* The SQL directly maps the source value without converting from ratio to percentage format
* This results in values that are 100x smaller than expected (e.g., 0.52 instead of 52)

---

## Evidence

**Key comparison demonstrating the error:**

| School CDSCode    | Source Value | Wrong Logic | Correct Logic | Ground Truth |
| ----------------- | ------------ | ----------- | ------------- | ------------ |
| 1100170109835     | 0.519779     | 0.52        | 51.98         | 51.98        |
| 1100170112607     | 0.470886     | 0.47        | 47.09         | 47.09        |
| 1100170118489     | 0.549180     | 0.55        | 54.92         | 54.92        |
| 1100170123968     | 0.591623     | 0.59        | 59.16         | 59.16        |
| 1100170124172     | 0.054475     | 0.05        | 5.45          | 5.45         |

**Data format verification from source:**
```
Sample FRPM records showing calculation:
CDSCode         Enrollment_K_12  Free_Meal_Count_K_12  Percent___Eligible_Free_K_12  Calculated %
1100170109835   1087             565                   0.519779                      51.98
1100170112607   395              186                   0.470886                      47.09
```

The source `Percent___Eligible_Free_K_12` = Free_Meal_Count / Enrollment, stored as a decimal.

**Impact:**
* Current implementation: **7,756/17,686 matches (43.9%)**
* Corrected implementation: **17,686/17,686 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The FRPM (Free or Reduced Price Meals) data stores percentage values as decimal ratios where 1.0 = 100%. The SQL must multiply by 100 to convert to actual percentage values that match the column's semantic meaning of "percentage of eligible free meals."
