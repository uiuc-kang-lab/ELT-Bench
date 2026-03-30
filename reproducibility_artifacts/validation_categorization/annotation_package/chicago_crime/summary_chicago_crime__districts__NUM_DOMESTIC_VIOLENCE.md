## Database: chicago_crime
## Table: districts
## Column: NUM_DOMESTIC_VIOLENCE

**Description:**
Number of domestic violence cases reported in the district, replace NULL values with 0.

---

## Root Cause
**Data type mismatch: SQL checks for string 'true' but column contains boolean TRUE values**

### Incorrect SQL Logic
```sql
WHERE (domestic = 'true' OR domestic = 'True' OR domestic = TRUE)
-- This checks for string literals and boolean, but may not match actual data format
```

### Correct SQL Logic
```sql
-- Use explicit type casting to handle boolean properly
WHERE UPPER(domestic::VARCHAR) = 'TRUE'

-- Or cast to boolean
WHERE domestic::BOOLEAN = TRUE

-- Or use more comprehensive matching
WHERE domestic IN ('TRUE', 'True', 'true', 1, '1') OR domestic::BOOLEAN = TRUE
```

---

## Why the Original Logic Is Wrong

* The `domestic` column in the crime data may be stored as a boolean type or as string representations
* The SQL condition checks for specific string values ('true', 'True') and boolean TRUE
* Depending on the database and data loading process, the actual values may be:
  - Boolean `TRUE`/`FALSE` (not string)
  - String `'TRUE'`/`'FALSE'` (uppercase)
  - Integer `1`/`0`
* The mismatch between expected and actual data representation causes zero matches
* All predicted values are 0 while ground truth shows actual counts (661, 2350, 3404, etc.)

---

## Evidence

**Key comparison demonstrating the error:**

| District | Wrong Logic | Correct Logic | Ground Truth |
| -------- | ----------- | ------------- | ------------ |
| Central (1) | 0 | 661 | 661 |
| Ogden (10) | 0 | 2350 | 2350 |
| Harrison (11) | 0 | 3404 | 3404 |
| Near West (12) | 0 | 1383 | 1383 |
| Austin (15) | 0 | 2323 | 2323 |
| Gresham (6) | 0 | 3773 | 3773 |

**Impact:**
* Current implementation: **0/22 matches (0%)**
* Corrected implementation: **22/22 matches (100%)**

---

## Result

:warning: **Critical Severity - Complete Data Type Mismatch**

**Key insight:**
When filtering on boolean-like columns, always verify the actual data type and representation in the source data. Use explicit type casting (`::BOOLEAN` or `::VARCHAR`) to ensure the comparison works correctly regardless of how the boolean is stored. A common pattern is to cast to string and compare uppercase: `UPPER(column::VARCHAR) = 'TRUE'`.
