# Column Mismatch Summary

## Database: movie
## Table: movie
## Column: PERCENTAGE_OF_THE_ACTOR_BORN_AFTER_19700101

### Description
The percentage of the actors that were born after 1970/1/1 in the credit list of the movie

---

## Root Cause
**GENUINE ERROR - Multiple issues in Pred SQL:**

1. **NULL↔0 handling** (154 movies): Pred uses COALESCE(..., 0) for movies without actors - this is a FALSE POSITIVE since the data model doesn't specify NULL vs 0 behavior
2. **Malformed date parsing** (causes 6 calculation errors): Source data contains dates like `1985-0-0` which GT parses correctly but Pred's `TRY_TO_DATE()` returns NULL
3. **Boundary condition**: GT uses `>= 1970-01-01`, Pred uses `> 1970-01-01`

---

## Issue 1: NULL↔0 Handling (FALSE POSITIVE - 154 movies)

The eval script's NULL↔0 equivalence handles this correctly. Movies without actors:
- GT: NULL
- Pred: 0.0
- **Status**: Matched by eval script (not an error)

---

## Issue 2: Malformed Date Parsing (GENUINE ERROR - 6 movies)

### Source Data Problem
The `actor.Date_of_Birth` column contains malformed dates in `YYYY-0-0` format:
```
Michael Conner Humphreys: 1985-0-0
Sam Anderson: 1984-0-0
Julia Hsu: 1986-0-0
Eric Gordon: 1988-0-0
... (35 total actors with this format)
```

### GT Logic (Correct)
GT extracts the year from the date string and compares:
```sql
-- Effectively: EXTRACT(YEAR FROM date_of_birth) >= 1970
```

### Pred Logic (Incorrect)
Pred uses `TRY_TO_DATE()` which returns NULL for malformed dates:
```sql
TRY_TO_DATE(a.date_of_birth) > '1970-01-01'
-- Returns NULL for '1985-0-0', so actor is not counted
```

---

## Issue 3: Boundary Condition

- **GT**: Counts actors born on or after 1970-01-01 (`>= 1970-01-01` or `year >= 1970`)
- **Pred**: Counts actors born strictly after 1970-01-01 (`> 1970-01-01`)

Example: Ken Leung (DOB: 1970-01-21)
- GT: Counts as born after 1970 (year 1970 >= 1970)
- Pred: Counts as born after 1970 (1970-01-21 > 1970-01-01) - happens to match in this case

---

## Evidence

**6 Movies with Calculation Errors:**

| MOVIEID | Title | GT | Pred | Cause |
|---------|-------|-----|------|-------|
| 112 | Forrest Gump | 22.22% (2/9) | 0.0% | 2 actors with `YYYY-0-0` dates not counted |
| 129 | Casper | 33.33% (3/9) | 22.22% | 1 actor with `YYYY-0-0` date not counted |
| 155 | Space Jam | 44.44% (4/9) | 33.33% | 1 actor with `YYYY-0-0` date not counted |
| 183 | Rush Hour | 33.33% (3/9) | 22.22% | 1 actor with `YYYY-0-0` date not counted |
| 304 | Meet the Fockers | 22.22% (2/9) | 0.0% | 2 actors with `YYYY-0-0` dates not counted |
| 377 | Slumdog Millionaire | 33.33% (3/9) | 22.22% | 1 actor with `YYYY-0-0` date not counted |

**Impact:**
* NULL↔0 cases: 154/154 matched (eval script handles this)
* Calculation errors: 6 movies have wrong percentages
* Overall: **628/634 matches (99.05%)** after NULL↔0 equivalence

---

## Result

**GENUINE ERROR** (for the 6 calculation mismatches)

The Pred SQL has two bugs:
1. `TRY_TO_DATE()` fails on malformed `YYYY-0-0` dates - should extract year instead
2. Uses `> '1970-01-01'` instead of `>= '1970-01-01'`

**Recommended fix:**
```sql
-- Instead of:
TRY_TO_DATE(a.date_of_birth) > '1970-01-01'

-- Use:
CAST(SPLIT_PART(a.date_of_birth, '-', 1) AS INT) >= 1970
```

**Category**: Should be moved from "False Positives - NULL Mismatch" to "Semantic Interpretation Errors - Logic (Flawed SQL)"
