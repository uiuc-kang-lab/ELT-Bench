# Column Mismatch Summary

## Database: california_schools
## Table: ca__schools
## Column: HAS_MORE_THAN_30_DIFFERENCE_IN_ENROLLMENTS_BETWEEN_K_12_AND_AGES_5_17

### Description
Set to 1 if the school has more than 30 differences in enrollments between K-12 and ages 5-17, otherwise, set to 0

---

## Root Cause
**NULL handling: COALESCE converts NULL enrollment to 0, incorrectly creating large differences**

### Incorrect SQL Logic
```sql
CASE
    WHEN ABS(COALESCE(f.Enrollment_K_12, 0) - COALESCE(f.Enrollment_Ages_5_17, 0)) > 30 THEN 1
    ELSE 0
END AS has_more_than_30_difference_in_enrollments_between_K_12_and_ages_5_17
```

### Correct SQL Logic
```sql
CASE
    WHEN f.Enrollment_K_12 IS NULL OR f.Enrollment_Ages_5_17 IS NULL THEN 0
    WHEN ABS(f.Enrollment_K_12 - f.Enrollment_Ages_5_17) > 30 THEN 1
    ELSE 0
END AS has_more_than_30_difference_in_enrollments_between_K_12_and_ages_5_17
```

---

## Why the Original Logic Is Wrong

* The SQL uses `COALESCE(Enrollment, 0)` which converts NULL enrollment values to 0
* When one enrollment field is NULL (typically `Enrollment_Ages_5_17`), this creates a false "difference" equal to the other enrollment value
* For example, if `Enrollment_K_12 = 160` and `Enrollment_Ages_5_17 = NULL`:
  * Wrong calculation: ABS(160 - 0) = 160 > 30 = **1** (incorrect)
  * Correct calculation: Either enrollment is NULL = **0** (correct)
* The ground truth treats NULL enrollment as "no data available" and returns 0 (cannot determine difference)

---

## Evidence

**Key comparison demonstrating the error:**

| School CDSCode    | Enrollment_K_12 | Enrollment_Ages_5_17 | Wrong Logic | Correct Logic | Ground Truth |
| ----------------- | --------------- | -------------------- | ----------- | ------------- | ------------ |
| 11101160002036    | 53              | NULL                 | 1           | 0             | 0            |
| 11101160002549    | 83              | NULL                 | 1           | 0             | 0            |
| 14101400009050    | 160             | NULL                 | 1           | 0             | 0            |
| 19647340139576    | 116             | NULL                 | 1           | 0             | 0            |
| 26102640001927    | 279             | NULL                 | 1           | 0             | 0            |
| 26102640001943    | 139             | NULL                 | 1           | 0             | 0            |
| 29102980004020    | 81              | NULL                 | 1           | 0             | 0            |
| 30665236059386    | 91              | NULL                 | 1           | 0             | 0            |
| 33672160004006    | 56              | NULL                 | 1           | 0             | 0            |

**NULL handling statistics:**
| Scenario                           | Count  | Wrong Logic Value | Ground Truth |
| ---------------------------------- | ------ | ----------------- | ------------ |
| Both enrollments have values       | 9,972  | Based on diff     | Based on diff|
| Only K_12 is NULL                  | 0      | N/A               | N/A          |
| Only Ages_5_17 is NULL             | 14     | 1 (if K_12 > 30)  | 0            |
| Both are NULL                      | 7,700  | 0                 | 0            |

**Value distributions:**
| Value | Ground Truth | Predicted (Wrong) |
| ----- | ------------ | ----------------- |
| 0     | 16,447       | 16,438            |
| 1     | 1,239        | 1,248             |

The 9 extra "1" values in predicted are all cases where `Enrollment_Ages_5_17` is NULL.

**Impact:**
* Current implementation: **17,677/17,686 matches (99.9%)**
* Corrected implementation: **17,686/17,686 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
When enrollment data is missing (NULL), the correct behavior is to return 0 (cannot determine if there's a difference). Using COALESCE to convert NULL to 0 incorrectly interprets "no data" as "zero students," which creates false positive differences.
