# Column Mismatch Summary

## Database: book_publishing_company
## Table: book_publishers
## Column: MOST_YTD_SALE_TITLE

### Description
The title of the book with the most year-to-date sales published by the publisher, with ties broken by the ascending order of the title.

---

## Root Cause
**NULL handling error: SQL filters out NULL ytd_sales, but GT treats NULL as highest value (NULLS FIRST semantics)**

### Incorrect SQL Logic
```sql
most_ytd_sale_book AS (
    SELECT
        pub_id,
        title,
        ytd_sales,
        ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY ytd_sales DESC, title ASC) as rn
    FROM titles_data
    WHERE ytd_sales IS NOT NULL  -- Excludes NULL ytd_sales
)
```

### Correct SQL Logic
```sql
most_ytd_sale_book AS (
    SELECT
        pub_id,
        title,
        ytd_sales,
        ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY ytd_sales DESC NULLS FIRST, title ASC) as rn
    FROM titles_data
    -- No WHERE filter - include NULL ytd_sales
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the book with the highest year-to-date sales for each publisher. The description doesn't specify NULL handling, but GT indicates NULL should be treated as "highest."

* **What the SQL actually computes**: The SQL filters out titles with NULL ytd_sales before ranking. This excludes titles that haven't been published yet or don't have sales data.

* **GT behavior**: Ground truth shows that for publishers 877 and 1389, the "most ytd sale title" is a book with NULL ytd_sales. This confirms GT uses `ORDER BY ytd_sales DESC NULLS FIRST` semantics.

---

## Evidence

**Key comparison demonstrating the error:**

| Publisher | PUB_NAME | Wrong Logic (excludes NULL) | Correct Logic (NULLS FIRST) | Ground Truth |
| --------- | -------- | --------------------------- | --------------------------- | ------------ |
| 877 | Binnet & Hardley | The Gourmet Microwave | The Psychology of Computer Cooking | The Psychology of Computer Cooking |
| 1389 | Algodata Infosystems | But Is It User Friendly? | Net Etiquette | Net Etiquette |

**Analysis:**
- Publisher 877: "The Psychology of Computer Cooking" has NULL ytd_sales (type = UNDECIDED, not yet published)
- Publisher 1389: "Net Etiquette" has NULL ytd_sales (not yet published)
- The SQL excludes these NULL ytd_sales titles, returning the next highest instead
- Note: Both publishers have the same pattern - a book with NULL values in price, royalty, and ytd_sales

**Impact:**
* Current implementation: **6/8 matches (75%)**
* Corrected implementation: **8/8 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
The ground truth treats NULL ytd_sales as "highest" priority, likely because:
1. These represent upcoming/unpublished books (type = UNDECIDED)
2. NULL in `ORDER BY ... DESC NULLS FIRST` sorts before non-NULL values

The fix is to either:
1. Use `ORDER BY ytd_sales DESC NULLS FIRST`
2. Use `ORDER BY COALESCE(ytd_sales, infinity) DESC`
3. Remove the `WHERE ytd_sales IS NOT NULL` filter

**Publishers where MOST_YTD_SALE_TITLE has NULL ytd_sales:**
- Publisher 877 (Binnet & Hardley): The Psychology of Computer Cooking (UNDECIDED type)
- Publisher 1389 (Algodata Infosystems): Net Etiquette (popular_comp type, likely pre-publication)

**Common pattern across all three book_publishers columns:**
All three columns (MOST_EXPENSIVE_BOOK, BOOK_HAS_THE_HIGHEST_ROYALTY, MOST_YTD_SALE_TITLE) return the same books for publishers 877 and 1389 because these books have NULL values for all relevant metrics (price, royalty, ytd_sales), and GT consistently treats NULL as "highest" in descending order.
