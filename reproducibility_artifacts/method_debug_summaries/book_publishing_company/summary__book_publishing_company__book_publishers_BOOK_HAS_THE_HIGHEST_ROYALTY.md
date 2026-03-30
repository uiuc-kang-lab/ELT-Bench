# Column Mismatch Summary

## Database: book_publishing_company
## Table: book_publishers
## Column: BOOK_HAS_THE_HIGHEST_ROYALTY

### Description
The title of the book with the highest royalty published by the publisher, with ties broken by the descending order of the title.

---

## Root Cause
**Two errors: (1) Uses ROYSCHED table instead of TITLES.royalty, and (2) Excludes NULL royalties but GT treats NULL as highest**

### Incorrect SQL Logic
```sql
roysched_data AS (
    SELECT
        title_id,
        royalty
    FROM {{ source('airbyte_schema', 'ROYSCHED') }}
),

title_max_royalty AS (
    SELECT
        title_id,
        MAX(royalty) as max_royalty
    FROM roysched_data
    GROUP BY title_id
),

highest_royalty_book AS (
    SELECT
        t.pub_id,
        t.title,
        tmr.max_royalty,
        ROW_NUMBER() OVER (PARTITION BY t.pub_id ORDER BY tmr.max_royalty DESC, t.title DESC) as rn
    FROM titles_data t
    INNER JOIN title_max_royalty tmr ON t.title_id = tmr.title_id
    -- INNER JOIN excludes titles not in ROYSCHED
)
```

### Correct SQL Logic
```sql
-- Use TITLES.royalty directly
highest_royalty_book AS (
    SELECT
        pub_id,
        title,
        royalty,
        ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY royalty DESC NULLS FIRST, title DESC) as rn
    FROM {{ source('airbyte_schema', 'TITLES') }}
    -- Include all titles, NULL royalty sorts first (highest)
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the book with the highest royalty rate for each publisher. The "royalty" here refers to the base royalty from the TITLES table, not the variable royalty schedules in ROYSCHED.

* **What the SQL actually computes**:
  1. Uses ROYSCHED table (royalty schedules with ranges) instead of TITLES.royalty
  2. Uses INNER JOIN which excludes titles without ROYSCHED entries
  3. Excludes titles with NULL royalty values

* **GT behavior**: Ground truth shows that for publishers 877 and 1389, the highest royalty book is one with NULL royalty value. This confirms GT uses TITLES.royalty with `NULLS FIRST` behavior.

---

## Evidence

**Key comparison demonstrating the error:**

| Publisher | PUB_NAME | Wrong Logic (ROYSCHED) | Correct Logic (TITLES.royalty, NULLS FIRST) | Ground Truth |
| --------- | -------- | ---------------------- | ------------------------------------------- | ------------ |
| 877 | Binnet & Hardley | The Gourmet Microwave | The Psychology of Computer Cooking | The Psychology of Computer Cooking |
| 1389 | Algodata Infosystems | Straight Talk About Computers | Net Etiquette | Net Etiquette |

**Analysis:**
- Publisher 877: "The Psychology of Computer Cooking" has NULL royalty in TITLES table
- Publisher 1389: "Net Etiquette" has NULL royalty in TITLES table
- The SQL uses ROYSCHED which doesn't include these NULL-royalty titles
- Additionally, tie-breaking is by descending title order (correct in SQL)

**Impact:**
* Current implementation: **6/8 matches (75%)**
* Corrected implementation: **8/8 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
Two issues compound:
1. **Wrong table**: The ROYSCHED table contains royalty schedules (variable rates by sales volume), not the title's base royalty rate
2. **NULL handling**: GT treats NULL royalty as "highest" using `NULLS FIRST` semantics

The fix requires using `TITLES.royalty` column directly with `ORDER BY royalty DESC NULLS FIRST, title DESC`.

**Publishers where BOOK_HAS_THE_HIGHEST_ROYALTY has NULL royalty:**
- Publisher 877 (Binnet & Hardley): The Psychology of Computer Cooking
- Publisher 1389 (Algodata Infosystems): Net Etiquette
