# Column Mismatch Summary

## Database: book_publishing_company
## Table: book_titles
## Column: SOLD_MORE_THAN_AVERAGE

### Description
Set to 1 if the title has sold more copies than the average number of copies sold by all titles; otherwise, set to 0.

---

## Root Cause
**Average calculation excludes titles without sales records, but should include ALL titles (treating missing sales as 0)**

### Incorrect SQL Logic
```sql
avg_sales_qty AS (
    SELECT
        AVG(total_qty) as avg_qty_sold
    FROM (
        SELECT
            title_id,
            SUM(qty) as total_qty
        FROM sales_data
        GROUP BY title_id
    )
    -- Only titles WITH sales records are in denominator
),

title_sales_summary AS (
    SELECT
        title_id,
        SUM(qty) as total_qty_sold,
        ...
    FROM sales_data
    GROUP BY title_id
),

-- Final comparison
CASE
    WHEN tss.total_qty_sold > (SELECT avg_qty_sold FROM avg_sales_qty) THEN 1
    ELSE 0
END as sold_more_than_average
```

### Correct SQL Logic
```sql
-- Include ALL titles in average calculation (treating no-sales as 0)
avg_sales_qty AS (
    SELECT
        AVG(COALESCE(total_qty, 0)) as avg_qty_sold
    FROM {{ source('airbyte_schema', 'TITLES') }} t
    LEFT JOIN (
        SELECT title_id, SUM(qty) as total_qty
        FROM {{ source('airbyte_schema', 'SALES') }}
        GROUP BY title_id
    ) s ON t.title_id = s.title_id
),

-- Final comparison
CASE
    WHEN COALESCE(tss.total_qty_sold, 0) > (SELECT avg_qty_sold FROM avg_sales_qty) THEN 1
    ELSE 0
END as sold_more_than_average
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: "average number of copies sold by ALL titles" - the average should be calculated across ALL titles in the TITLES table, including those with zero sales.

* **What the SQL actually computes**: The SQL calculates average only over titles that have at least one record in the SALES table. This inflates the average because titles with no sales are excluded from the denominator.

* **Example impact**:
  - If 18 titles exist but only 12 have sales records
  - Current: avg = sum(sales) / 12 (higher average)
  - Correct: avg = sum(sales) / 18 (lower average, more titles qualify as "above average")

---

## Evidence

**Key comparison demonstrating the error:**

| TITLE_ID | Title | Total Qty Sold | Wrong Avg (sales only) | Correct Avg (all titles) | GT |
| -------- | ----- | -------------- | ---------------------- | ------------------------ | -- |
| BU1111 | Cooking with Computers | ~X | Above avg=0 | Above avg=1 | 1 |
| PC1035 | But Is It User Friendly? | ~X | Above avg=0 | Above avg=1 | 1 |
| PS2106 | Life Without Fear | ~X | Above avg=0 | Above avg=1 | 1 |
| PS7777 | Emotional Security | ~X | Above avg=0 | Above avg=1 | 1 |

**Pattern:**
- GT shows 9 titles with value=1 (half of 18 titles)
- Predicted shows only 5 titles with value=1
- The titles marked as 1 in GT but 0 in Pred are those that fall BETWEEN the two averages

**Impact:**
* Current implementation: **14/18 matches (77.8%)**
* Corrected implementation: **18/18 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
The phrase "average number of copies sold by all titles" means the denominator should include ALL titles from the TITLES table, treating titles without sales records as having sold 0 copies. This results in a lower average, causing more titles to qualify as "sold more than average."

**Titles with SOLD_MORE_THAN_AVERAGE = 1:**
- BU1111: Cooking with Computers: Surreptitious Balance Sheets
- BU2075: You Can Combat Computer Stress!
- MC3021: The Gourmet Microwave
- PC1035: But Is It User Friendly?
- PC8888: Secrets of Silicon Valley
- PS2091: Is Anger the Enemy?
- PS2106: Life Without Fear
- PS7777: Emotional Security: A New Algorithm
- TC3218: Onions, Leeks, and Garlic
