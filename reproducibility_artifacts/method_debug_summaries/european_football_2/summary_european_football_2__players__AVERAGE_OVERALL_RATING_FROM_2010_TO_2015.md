# Column Mismatch Summary

## Database: european_football_2
## Table: players
## Column: AVERAGE_OVERALL_RATING_FROM_2010_TO_2015

**Description:**
The average overall rating the player received from 2010 to 2015, calculated from the player_attributes table.

---

## Root Cause
**FALSE POSITIVE - GT has a calculation bug, Pred is correct**

Two issues identified:
1. **NULL↔0 handling** (357 players): Pred uses COALESCE(..., 0), GT preserves NULL - this is a FALSE POSITIVE (eval script handles this)
2. **GT calculation bug** (32 players): GT divides by total record count instead of non-null record count

---

## Issue 1: NULL↔0 Handling (FALSE POSITIVE - 357 players)

Players without any rating records in 2010-2015:
- GT: NULL
- Pred: 0.0
- **Status**: Matched by eval script's NULL↔0 equivalence

---

## Issue 2: GT Calculation Bug (FALSE POSITIVE - 32 players)

### The Problem
The `Player_Attributes` table contains **duplicate records** for many players - each date has two entries: one with ratings and one with NULL ratings.

Example for Player 110189:
```
Date                 overall_rating
2015-11-06           78.0
2015-11-06           NULL (duplicate)
2015-10-16           78.0
2015-10-16           NULL (duplicate)
...
```

### GT Logic (INCORRECT)
GT appears to calculate: `SUM(overall_rating) / COUNT(*)`
- This divides by total record count (including NULL ratings)
- For Player 110189: 1774 / 46 = **38.57**

### Pred Logic (CORRECT)
Pred uses standard SQL AVG: `AVG(overall_rating)` = `SUM(overall_rating) / COUNT(overall_rating)`
- This divides by non-null record count only
- For Player 110189: 1774 / 23 = **77.13**

---

## Evidence

**Sample players with GT calculation bug:**

| Player API ID | Total Records | Non-NULL Records | GT Value | Pred Value | GT Calculation | Pred Calculation |
|---------------|---------------|------------------|----------|------------|----------------|------------------|
| 110189 | 46 | 23 | 38.57 | 77.13 | 1774/46 | 1774/23 |
| 193866 | 38 | 19 | 35.71 | 71.42 | SUM/38 | SUM/19 |

**Verification:**
```python
# For Player 110189:
sum_ratings = 1774.0
total_records = 46
non_null_records = 23

gt_calc = sum_ratings / total_records      # = 38.57 (matches GT)
pred_calc = sum_ratings / non_null_records # = 77.13 (matches Pred)
```

**Impact:**
* NULL↔0 cases: 357/357 matched (eval script handles this)
* GT bug cases: 32 players have incorrect GT values
* Overall: **11,028/11,060 matches (99.71%)** after NULL↔0 equivalence

---

## Result

**FALSE POSITIVE - GT has a bug, Pred is correct**

The GT calculation incorrectly divides by total record count instead of non-null record count. This is a standard SQL AVG() behavior issue:
- `AVG(column)` should ignore NULL values in both numerator AND denominator
- GT appears to use `SUM(column) / COUNT(*)` which includes NULL records in denominator

**Recommendation**: Generate a new GT table with corrected AVG calculation.

**Category**: Should remain in "False Positives - NULL Mismatch" (or move to a new "GT Quality Issues" category)
