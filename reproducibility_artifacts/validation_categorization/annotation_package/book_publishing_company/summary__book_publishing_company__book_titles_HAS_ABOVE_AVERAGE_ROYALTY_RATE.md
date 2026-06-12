# Column Mismatch Summary

## Database: book_publishing_company
## Table: book_titles
## Column: HAS_ABOVE_AVERAGE_ROYALTY_RATE

### Description
Set to 1 if the royalty rate of the title is above the average royalty rate of all titles; otherwise, set to 0.

---

## Root Cause
**Wrong table used: SQL uses ROYSCHED table (royalty schedules) instead of TITLES table (title royalty rate)**

### Incorrect SQL Logic
```sql
roysched_data AS (
    SELECT
        title_id,
        royalty
    FROM {{ source('airbyte_schema', 'ROYSCHED') }}
),

avg_royalty AS (
    SELECT
        AVG(royalty) as avg_royalty_rate
    FROM roysched_data
    WHERE royalty IS NOT NULL
),

title_royalty AS (
    SELECT
        title_id,
        AVG(royalty) as avg_title_royalty
    FROM roysched_data
    GROUP BY title_id
)

-- Final comparison
CASE
    WHEN tr.avg_title_royalty > (SELECT avg_royalty_rate FROM avg_royalty) THEN 1
    ELSE 0
END as has_above_average_royalty_rate
```

### Correct SQL Logic
```sql
-- Use TITLES.royalty directly (single royalty per title)
avg_royalty AS (
    SELECT
        AVG(royalty) as avg_royalty_rate
    FROM {{ source('airbyte_schema', 'TITLES') }}
    WHERE royalty IS NOT NULL
)

-- Final comparison
CASE
    WHEN t.royalty > (SELECT avg_royalty_rate FROM avg_royalty) THEN 1
    ELSE 0
END as has_above_average_royalty_rate
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Compare each title's royalty rate (from TITLES table) against the average royalty rate across all titles.

* **What the SQL actually computes**: The SQL uses the ROYSCHED table, which contains royalty **schedules** with multiple rows per title (based on sales volume ranges: lorange, hirange). The SQL then averages these schedule entries per title, which is semantically different from the title's base royalty rate.

* **Schema evidence**:
  - `TITLES` table has a `royalty` column: "royalty" - the title's royalty rate
  - `ROYSCHED` table has `royalty` column with `lorange` and `hirange`: This is a royalty schedule table where royalty varies by sales volume

---

## Evidence

**Key comparison demonstrating the error:**

| TITLE_ID | Title | ROYSCHED Logic | TITLES.royalty Logic | Ground Truth |
| -------- | ----- | -------------- | -------------------- | ------------ |
| BU1111 | Cooking with Computers | 1 | 0 | 0 |
| BU7832 | Straight Talk About Computers | 1 | 0 | 0 |
| PC1035 | But Is It User Friendly? | 0 | 1 | 1 |
| TC3218 | Onions, Leeks, and Garlic | 1 | 0 | 0 |

**Analysis:**
- ROYSCHED may have multiple entries per title with varying royalty percentages
- The average of ROYSCHED royalties differs from the single TITLES.royalty value
- GT uses TITLES.royalty for the comparison

**Impact:**
* Current implementation: **14/18 matches (77.8%)**
* Corrected implementation: **18/18 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
The `ROYSCHED` table contains royalty **schedules** (multiple rows per title with royalty rates that vary by sales volume range), while the `TITLES` table contains the **base royalty rate** for each title. The column description refers to "the royalty rate of the title" which is the single value in `TITLES.royalty`, not the averaged schedule values.

**Titles with HAS_ABOVE_AVERAGE_ROYALTY_RATE = 1:**
- BU2075: You Can Combat Computer Stress!
- MC3021: The Gourmet Microwave
- PC1035: But Is It User Friendly?
- TC4203: Fifty Years in Buckingham Palace Kitchens
