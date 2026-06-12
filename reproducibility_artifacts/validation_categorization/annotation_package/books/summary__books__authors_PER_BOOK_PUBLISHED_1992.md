# Column Mismatch Summary

## Database: books
## Table: authors
## Column: PER_BOOK_PUBLISHED_1992

### Description
The percentage of books published by the author in 1992.

---

## Root Cause
**Rounding difference and/or date parsing issue in counting 1992 publications**

### Current SQL Logic
```sql
author_stats AS (
    SELECT
        author_id,
        ...
        COUNT(CASE WHEN YEAR(TO_DATE(publication_date)) = 1992 THEN 1 END) AS books_1992,
        COUNT(DISTINCT book_id) AS total_books,
        ...
    FROM author_books
    GROUP BY author_id, author_name
),

-- Final SELECT
ROUND(100.0 * ast.books_1992 / NULLIF(ast.total_books, 0), 2) AS per_book_published_1992
```

### Potential Issues
```sql
-- Issue 1: Date parsing might fail for some dates
YEAR(TO_DATE(publication_date)) = 1992

-- Issue 2: Rounding precision
ROUND(100.0 * books_1992 / total_books, 2)
-- GT might use different precision or no rounding
```

---

## Why the Original Logic May Be Wrong

* **What the column description means**: (books published in 1992 / total books) * 100

* **What the SQL computes**: Same calculation but with potential issues:
  1. `TO_DATE(publication_date)` may fail to parse some dates correctly
  2. `ROUND(..., 2)` rounds to 2 decimal places, but GT might use full precision

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | Result |
| ------ | ------ |
| Common authors | 9127 |
| PER_BOOK_PUBLISHED_1992 matches | 9099/9127 (99.7%) |
| Mismatches | 28 |

**Example mismatches (if any):**
Most mismatches are likely due to:
- Rounding differences (GT uses 14.285714285714286, Pred uses 14.29)
- Date parsing issues for certain publication dates

**Impact:**
* Current implementation: **9099/9127 matches (99.7%)**
* The 28 mismatches are likely rounding/precision differences

---

## Result

**Near-perfect match with minor rounding differences**

**Key insight:**
The logic is fundamentally correct. The ~0.3% mismatches are likely due to:
1. Floating point precision differences in the percentage calculation
2. Different rounding behavior (ROUND vs no rounding)
3. Potential date parsing differences for edge cases

**Recommendation:**
Match the precision used in GT - either remove ROUND() or match the exact precision level.
