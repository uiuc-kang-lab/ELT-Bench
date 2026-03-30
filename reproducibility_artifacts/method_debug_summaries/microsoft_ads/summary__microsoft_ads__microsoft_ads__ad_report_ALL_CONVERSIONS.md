# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
## Column: ALL_CONVERSIONS

**Description:**
Number of all conversions, measured by completion of an action by a customer after viewing your ad. This will include data from conversions regardless of the value of the conversion goal's ExcludeFromBidding property in Microsoft Ads. This field coalesces the source all_conversions_qualified and all_conversions fields, and will be 0 if both are null.

---

## Root Cause
**Wrong coalesce order: SQL uses `all_conversions` directly instead of coalescing `all_conversions_qualified` first then `all_conversions`**

### Incorrect SQL Logic
```sql
SELECT
    ...
    COALESCE(all_conversions, 0) AS all_conversions,  -- WRONG: uses all_conversions directly
    ...
FROM ad_performance_daily_report
```

### Correct SQL Logic
```sql
SELECT
    ...
    COALESCE(all_conversions_qualified, all_conversions, 0) AS all_conversions,  -- CORRECT: coalesce order
    ...
FROM ad_performance_daily_report
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "This field coalesces the source `all_conversions_qualified` and `all_conversions` fields"
  * Priority: use `all_conversions_qualified` if available, then fall back to `all_conversions`
  * Both fields include ALL conversions (regardless of ExcludeFromBidding)
  * `all_conversions_qualified` is the newer/preferred field

* **What the SQL actually computes:**
  * Uses only the `all_conversions` source field directly
  * Ignores `all_conversions_qualified` entirely
  * Returns different value when both fields have different values

**Source data example:**
| all_conversions_qualified | all_conversions | GT ALL_CONVERSIONS | Predicted ALL_CONVERSIONS |
| ------------------------- | --------------- | ------------------ | ------------------------- |
| 3.0 | 4.0 | 3 | 4 |
| 0.0 | 0.0 | 0 | 0 |

---

## Evidence

**Key comparison demonstrating the error:**

| Index | GT ALL_CONVERSIONS | Predicted ALL_CONVERSIONS | all_conversions_qualified | all_conversions |
| ----- | ------------------ | ------------------------- | ------------------------- | --------------- |
| 41 | 3 | 4 | 3.0 | 4.0 |

**Impact:**
* Current implementation: **311/312 matches (99.7%)**
* Corrected implementation: **312/312 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing from `COALESCE(all_conversions, 0)` to `COALESCE(all_conversions_qualified, all_conversions, 0)` to properly implement the field coalesce priority as described in the column specification.
