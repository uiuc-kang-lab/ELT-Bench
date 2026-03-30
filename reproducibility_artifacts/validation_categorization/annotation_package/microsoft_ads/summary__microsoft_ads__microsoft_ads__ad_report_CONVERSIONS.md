# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__ad_report
## Column: CONVERSIONS

**Description:**
Number of conversions, measured by completion of an action by a customer after viewing your ad. This will exclude any conversions where the conversion goal's ExcludeFromBidding property in Microsoft Ads is set to true. This field coalesces the source conversions_qualified and conversions fields, and will be 0 if both are null.

---

## Root Cause
**Wrong coalesce order: SQL uses `conversions` directly instead of coalescing `conversions_qualified` first then `conversions`**

### Incorrect SQL Logic
```sql
SELECT
    ...
    COALESCE(conversions, 0) AS conversions,  -- WRONG: uses conversions directly
    ...
FROM ad_performance_daily_report
```

### Correct SQL Logic
```sql
SELECT
    ...
    COALESCE(conversions_qualified, conversions, 0) AS conversions,  -- CORRECT: coalesce order
    ...
FROM ad_performance_daily_report
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "This field coalesces the source `conversions_qualified` and `conversions` fields"
  * Priority: use `conversions_qualified` if available, then fall back to `conversions`
  * Both fields represent conversions excluding ExcludeFromBidding goals
  * `conversions_qualified` is the newer/preferred field

* **What the SQL actually computes:**
  * Uses only the `conversions` source field directly
  * Ignores `conversions_qualified` entirely
  * Returns different value when both fields have different values

**Source data example:**
| conversions_qualified | conversions | GT CONVERSIONS | Predicted CONVERSIONS |
| --------------------- | ----------- | -------------- | --------------------- |
| 1.0 | 2.0 | 1 | 2 |
| 0.0 | 0.0 | 0 | 0 |

---

## Evidence

**Key comparison demonstrating the error:**

| Index | GT CONVERSIONS | Predicted CONVERSIONS | conversions_qualified | conversions |
| ----- | -------------- | --------------------- | --------------------- | ----------- |
| 41 | 1 | 2 | 1.0 | 2.0 |

**Impact:**
* Current implementation: **311/312 matches (99.7%)**
* Corrected implementation: **312/312 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing from `COALESCE(conversions, 0)` to `COALESCE(conversions_qualified, conversions, 0)` to properly implement the field coalesce priority as described in the column specification.
