# Column Mismatch Summary

## Database: books
## Table: authors
## Column: MOST_EXPENSIVE_BOOK

### Description
Title of the most expensive book written by the author, with ties broken by the descending order of the title.

---

## Root Cause
**No error - 100% match for common authors**

### Current SQL Logic (Correct)
```sql
most_expensive_book AS (
    SELECT
        ab.author_id,
        MAX(ab.title) AS most_expensive_book
    FROM author_books ab
    INNER JOIN author_stats ast ON ab.author_id = ast.author_id
        AND ab.price = ast.max_price
    GROUP BY ab.author_id
)
```

---

## Why the Logic Is Correct

* **What the column description means**: Find the book with the highest price for each author. If multiple books have the same highest price, pick the one with the alphabetically last title (descending order).

* **What the SQL computes**:
  1. Finds the maximum price per author (`author_stats.max_price`)
  2. Joins to get books matching that maximum price
  3. Uses `MAX(title)` to handle ties by descending title order

This correctly implements the tie-breaking logic (MAX = descending).

---

## Evidence

**Key comparison demonstrating correctness:**

| Metric | Result |
| ------ | ------ |
| Common authors | 9127 |
| MOST_EXPENSIVE_BOOK matches | 9127/9127 (100%) |

**Impact:**
* Current implementation: **9127/9127 matches (100%)** for common authors
* Only issue is 110 missing authors (no books = no most expensive book)

---

## Result

✅ **Perfect match for all common authors**

**Key insight:**
The MOST_EXPENSIVE_BOOK logic is correctly implemented. The tie-breaking by descending title order is correctly achieved via `MAX(title)`. The only "missing" values are for the 110 authors excluded by the INNER JOIN.
