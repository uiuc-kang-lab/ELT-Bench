# Column Mismatch Summary

## Database: book_publishing_company
## Table: book_publishers
## Column: MOST_EXPENSIVE_BOOK

### Description
The title of the most expensive book published by the publisher, with ties broken by the ascending order of the title.

---

## Root Cause
**NULL handling error: SQL filters out NULL prices, but GT treats NULL as highest value (NULL sorts last in DESC order without NULLS FIRST)**

### Incorrect SQL Logic
```sql
most_expensive_book AS (
    SELECT
        pub_id,
        title,
        price,
        ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY price DESC, title ASC) as rn
    FROM titles_data
    WHERE price IS NOT NULL  -- Excludes NULL prices
)
```

### Correct SQL Logic
```sql
most_expensive_book AS (
    SELECT
        pub_id,
        title,
        price,
        ROW_NUMBER() OVER (PARTITION BY pub_id ORDER BY price DESC NULLS FIRST, title ASC) as rn
    FROM titles_data
    -- No WHERE filter - include NULL prices
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the most expensive book for each publisher. The description doesn't explicitly state NULL handling, but GT indicates NULL prices should be treated as "most expensive" (or highest priority).

* **What the SQL actually computes**: The SQL filters out titles with NULL prices before ranking. This means titles with NULL prices are never considered as candidates for "most expensive."

* **GT behavior**: The ground truth shows that for publishers 877 and 1389, the "most expensive book" is a title with NULL price. This indicates GT uses `ORDER BY price DESC NULLS FIRST` semantics - NULL values sort before non-NULL values in descending order.

---

## Evidence

**Key comparison demonstrating the error:**

| Publisher | PUB_NAME | Wrong Logic (excludes NULL) | Correct Logic (NULLS FIRST) | Ground Truth |
| --------- | -------- | --------------------------- | --------------------------- | ------------ |
| 877 | Binnet & Hardley | Computer Phobic AND Non-Phobic Individuals | The Psychology of Computer Cooking | The Psychology of Computer Cooking |
| 1389 | Algodata Infosystems | But Is It User Friendly? | Net Etiquette | Net Etiquette |

**Analysis:**
- Publisher 877: "The Psychology of Computer Cooking" likely has NULL price
- Publisher 1389: "Net Etiquette" likely has NULL price
- The SQL excludes these NULL-priced books, returning the next highest-priced book instead

**Impact:**
* Current implementation: **6/8 matches (75%)**
* Corrected implementation: **8/8 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
In SQL, NULL handling in ORDER BY is database-specific. The ground truth expects `NULLS FIRST` behavior in descending order, meaning titles with NULL prices are considered "most expensive." The fix is to either:
1. Use `ORDER BY price DESC NULLS FIRST`
2. Use `ORDER BY COALESCE(price, infinity) DESC`
3. Remove the `WHERE price IS NOT NULL` filter

**Publishers where MOST_EXPENSIVE_BOOK has NULL price:**
- Publisher 877 (Binnet & Hardley): The Psychology of Computer Cooking
- Publisher 1389 (Algodata Infosystems): Net Etiquette
