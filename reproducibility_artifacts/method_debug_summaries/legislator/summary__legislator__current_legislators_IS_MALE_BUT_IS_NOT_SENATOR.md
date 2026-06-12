# Column Mismatch Summary

## Database: legislator
## Table: current_legislators
## Column: IS_MALE_BUT_IS_NOT_SENATOR

**Description:**
Set to 1 if the current legislator is male but is not a senator, 0 otherwise.

---

## Root Cause
**Wrong column used: SQL checks `TITLE = 'Sen'` but `title` contains leadership roles (e.g., "Majority Whip"), not legislator type. Should check `TYPE = 'sen'` instead.**

### Incorrect SQL Logic
```sql
-- In senator detection CTE:
MAX(CASE WHEN TITLE = 'Sen' THEN 1 ELSE 0 END) as is_senator_current

-- Then in final select:
CASE WHEN l.GENDER_BIO = 'M' AND COALESCE(ct.is_senator_current, 0) = 0 THEN 1 ELSE 0 END AS is_male_but_is_not_senator
```

### Correct SQL Logic
```sql
-- In senator detection CTE:
MAX(CASE WHEN TYPE = 'sen' THEN 1 ELSE 0 END) as is_senator_current

-- Then in final select:
CASE WHEN l.GENDER_BIO = 'M' AND COALESCE(ct.is_senator_current, 0) = 0 THEN 1 ELSE 0 END AS is_male_but_is_not_senator
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Check if legislator's gender is male (gender_bio = 'M')
  * Check if legislator is NOT a senator
  * Return 1 if both conditions are true, 0 otherwise

* **What the SQL actually computes:**
  * Correctly checks gender_bio = 'M'
  * Incorrectly uses `TITLE` column to detect senators
  * The `TITLE` column contains leadership/committee titles (e.g., "Majority Whip", "Ranking Member"), not legislator type
  * Most senators have NULL in the `TITLE` column
  * The `TYPE` column contains the actual legislator type: 'rep' or 'sen'

**Column semantics from source schema:**
| Column | Purpose | Values |
| ------ | ------- | ------ |
| title | Leadership/committee titles | "Majority Whip", "Minority Leader", etc. (often NULL) |
| type | Legislator type | 'rep' (2770 records), 'sen' (244 records) |

**Title column value distribution:**
- Most entries are NULL
- Non-NULL values are leadership titles, not legislator types

---

## Evidence

**Key comparison demonstrating the error:**

| BIOGUIDE_ID | Gender | Type | Title | GT | Predicted |
| ----------- | ------ | ---- | ----- | -- | --------- |
| B001135 | M | sen | NaN | 0 | 1 |
| B001230 | F | sen | NaN | 0 | 0 |
| B001236 | M | sen | NaN | 0 | 1 |
| B001243 | F | sen | NaN | 0 | 0 |
| B001261 | M | sen | NaN | 0 | 1 |
| B001267 | M | sen | NaN | 0 | 1 |
| B001277 | M | sen | NaN | 0 | 1 |
| B001288 | M | sen | NaN | 0 | 1 |

**Pattern analysis:**
- All 33 mismatches are male senators (gender_bio = 'M', type = 'sen')
- Their `title` column is NULL (no leadership position)
- SQL incorrectly marks them as non-senators because `TITLE != 'Sen'`
- GT correctly identifies them as senators (value = 0)

**Test results:**
| Method | Match Rate |
| ------ | ---------- |
| Gender='M' AND NOT Senator (by title) | 508/541 (93.9%) |
| Gender='M' AND NOT Senator (by type) | 541/541 (100.0%) |

**Impact:**
* Current implementation: **508/541 matches (93.9%)**
* Corrected implementation: **541/541 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that the `title` column contains leadership roles and committee positions, not the legislator's chamber membership. The `type` column correctly identifies whether someone is a senator ('sen') or representative ('rep'). Changing from `TITLE = 'Sen'` to `TYPE = 'sen'` achieves 100% accuracy.

**Legislators incorrectly classified (male senators marked as non-senators):**
- 33 male senators with NULL title values
- Examples: Richard Burr (B001135), John Barrasso (B001261), Michael Bennet (B001267), Richard Blumenthal (B001277), Cory Booker (B001288)
