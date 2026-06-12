## Database: chicago_crime
## Table: districts
## Column: DIFF_BEWTEEN_VEHICULAR_HIJACKINGS_AND_AGGRAVATED_VEHICULAR_HIJACKINGS

**Description:**
Difference between the number of vehicular hijackings and the number of aggravated vehicular hijackings reported in the district.

---

## Root Cause
**Data type difference: Ground truth uses float (-1.0) while predicted uses integer (-1)**

### Incorrect SQL Logic
```sql
COUNT(CASE WHEN secondary_description = 'VEHICULAR HIJACKING' THEN 1 END) -
COUNT(CASE WHEN secondary_description = 'AGGRAVATED VEHICULAR HIJACKING' THEN 1 END) AS diff
```

### Correct SQL Logic
```sql
-- Cast to float/decimal to match GT format
CAST(
    COUNT(CASE WHEN secondary_description = 'VEHICULAR HIJACKING' THEN 1 END) -
    COUNT(CASE WHEN secondary_description = 'AGGRAVATED VEHICULAR HIJACKING' THEN 1 END)
AS DECIMAL(10,1)) AS diff
```

---

## Why the Original Logic Is Wrong

* The calculation logic is semantically correct - the difference values are mathematically equivalent
* The issue is a data type mismatch: ground truth stores values as floats (e.g., -1.0, -12.0)
* Predicted values are integers (e.g., -1, -12)
* When comparing `-1` (int) vs `-1.0` (float), string comparison may fail
* This is a minor formatting/type issue, not a logic error

---

## Evidence

**Key comparison demonstrating the error:**

| District | Wrong Logic | Correct Logic | Ground Truth |
| -------- | ----------- | ------------- | ------------ |
| Central (1) | -1 | -1.0 | -1.0 |
| Ogden (10) | -12 | -12.0 | -12.0 |
| Harrison (11) | -26 | -26.0 | -26.0 |
| Near North (18) | 1 | 1.0 | 1.0 |

**Impact:**
* Current implementation: **0/22 matches (0%)** - due to type comparison
* Corrected implementation: **22/22 matches (100%)**

---

## Result

:warning: **Low Severity - Data Type Difference Only**

**Key insight:**
The calculated values are numerically correct. The mismatch is caused by data type representation differences between integer and float. Either cast the result to a decimal/float type or ensure consistent type handling in the comparison logic.
