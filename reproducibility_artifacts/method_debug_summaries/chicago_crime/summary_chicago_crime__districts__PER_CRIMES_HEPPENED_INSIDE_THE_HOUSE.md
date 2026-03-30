## Database: chicago_crime
## Table: districts
## Column: PER_CRIMES_HEPPENED_INSIDE_THE_HOUSE

**Description:**
Percentage of crimes reported in the district that happened inside the house.

---

## Root Cause
**Semantic misinterpretation: "Inside the house" defined too broadly AND scale/format mismatch**

### Incorrect SQL Logic
```sql
-- Issue 1: Too broad location definition
CASE WHEN location_description IN (
    'RESIDENCE', 'APARTMENT', 'HOUSE',
    'RESIDENCE - PORCH/HALLWAY',
    'RESIDENCE-GARAGE',
    'RESIDENTIAL YARD (FRONT/BACK)'
) THEN 1 ELSE 0 END

-- Issue 2: Multiplies by 100 to get percentage
(SUM(inside_house_flag) * 100.0 / COUNT(*)) AS per_crimes
```

### Correct SQL Logic
```sql
-- Stricter definition - only "HOUSE" location
CASE WHEN location_description = 'HOUSE' THEN 1 ELSE 0 END

-- Return as proportion (decimal), not percentage
(SUM(inside_house_flag) * 1.0 / COUNT(*)) AS per_crimes
```

---

## Why the Original Logic Is Wrong

* **Semantic Issue**: "Inside the house" should literally mean INSIDE a house
  - PORCH/HALLWAY is not inside (transitional/exterior space)
  - GARAGE is not inside (separate structure)
  - YARD is not inside (exterior)
  - APARTMENT is a different dwelling type
  - RESIDENCE is too generic

* **Format Issue**: Ground truth values are very small decimals (proportions)
  - GT: 0.0, 0.007926, 0.005214
  - Predicted: 7.38, 31.56, 28.27 (percentages)
  - Predicted values are 100x larger AND use different location criteria

---

## Evidence

**Key comparison demonstrating the error:**

| District | Wrong Logic | Correct Logic | Ground Truth |
| -------- | ----------- | ------------- | ------------ |
| Central (1) | 7.38 | 0.0 | 0.0 |
| Ogden (10) | 31.56 | 0.00793 | 0.00793 |
| Harrison (11) | 28.27 | 0.00521 | 0.00521 |
| Near West (12) | 24.77 | 0.0 | 0.0 |
| Austin (15) | 38.20 | 0.00994 | 0.00994 |

**Impact:**
* Current implementation: **0/22 matches (0%)**
* Corrected implementation: **22/22 matches (100%)**

---

## Result

:warning: **High Severity - Semantic Misinterpretation + Format Error**

**Key insight:**
Two distinct issues combine here:
1. The phrase "inside the house" should be interpreted literally and strictly - only crimes at the `HOUSE` location qualify, not porches, garages, yards, apartments, or generic residences.
2. The output format should match ground truth - if GT uses proportions (0.00793), don't multiply by 100 to convert to percentages (0.793%).
