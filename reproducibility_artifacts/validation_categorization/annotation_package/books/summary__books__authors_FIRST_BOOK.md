# Column Mismatch Summary

## Database: books
## Table: authors
## Column: FIRST_BOOK

### Description
Title of the first book written by the author, with ties broken by the ascending order of the title.

---

## Root Cause
**No error in logic - 100% match for common authors. Only issue is missing authors due to INNER JOIN**

### Current SQL Logic (Correct for present authors)
```sql
first_book AS (
    SELECT
        ab.author_id,
        MIN(ab.title) AS first_book
    FROM author_books ab
    INNER JOIN author_stats ast ON ab.author_id = ast.author_id
        AND ab.publication_date = ast.first_publication_date
    GROUP BY ab.author_id
)
```

---

## Why the Logic Is Correct

* **What the column description means**: Find the earliest published book by each author. If multiple books were published on the same date, pick the one with the alphabetically first title.

* **What the SQL computes**:
  1. Finds the minimum (earliest) publication_date per author (`author_stats.first_publication_date`)
  2. Joins to get books matching that earliest date
  3. Uses `MIN(title)` to handle ties by ascending title order

This correctly implements the tie-breaking logic.

---

## Evidence

**Key comparison demonstrating correctness:**

| Metric | Result |
| ------ | ------ |
| Common authors | 9127 |
| FIRST_BOOK matches | 9127/9127 (100%) |

**All FIRST_BOOK values match for authors present in both GT and Pred.**

**Impact:**
* Current implementation: **9127/9127 matches (100%)** for common authors
* 110 missing authors have NULL FIRST_BOOK in GT (authors with no books)

---

## Result

✅ **Perfect match for all common authors**

**Key insight:**
The FIRST_BOOK logic is correctly implemented. The tie-breaking by ascending title order is achieved via `MIN(title)`. The only "mismatches" are the 110 missing authors who have no books at all.
