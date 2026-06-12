# Column Mismatch Summary

## Database: books
## Table: authors
## Column: AUTHOR_ID

### Description
Unique identifier for the author.

---

## Root Cause
**Missing rows: 110 authors exist in GT but not in Pred due to INNER JOIN filtering out authors with no books**

### Incorrect SQL Logic
```sql
author_books AS (
    SELECT
        a.author_id,
        a.author_name,
        ...
    FROM author_data a
    INNER JOIN book_author_data ba ON a.author_id = ba.author_id
    INNER JOIN book_data b ON ba.book_id = b.book_id
    ...
)

-- The query starts from author_stats which is built from author_books
SELECT
    ast.author_id,
    ...
FROM author_stats ast
```

### Correct SQL Logic
```sql
-- Use LEFT JOINs to include all authors, even those without books
author_books AS (
    SELECT
        a.author_id,
        a.author_name,
        ...
    FROM author_data a
    LEFT JOIN book_author_data ba ON a.author_id = ba.author_id
    LEFT JOIN book_data b ON ba.book_id = b.book_id
    ...
)

-- Or start from author_data directly
SELECT
    a.author_id,
    a.author_name,
    ...
FROM author_data a
LEFT JOIN author_stats ast ON a.author_id = ast.author_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Every author in the `author` source table should appear in the output with their unique identifier.

* **What the SQL actually computes**: The SQL uses INNER JOINs between `author`, `book_author`, and `book` tables. This means only authors who have at least one book entry in `book_author` AND that book exists in `book` table will appear in the results.

* **Schema evidence**: Authors may exist in the database without any published books (new authors, authors whose books were removed, etc.). The INNER JOIN filters these out.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total authors | 9237 | 9125 |
| Missing authors | 0 | 110 |

**Example missing authors (IDs):**
- Author ID 40 (Adam Drozdek) - exists in GT, missing in Pred
- Author ID 61 (Adèle Geras) - exists in GT, missing in Pred
- Author ID 78 (Aesop) - exists in GT, missing in Pred

**Impact:**
* Current implementation: **9125/9237 rows (98.8%)** - 110 authors missing
* Corrected implementation: **9237/9237 rows (100%)**

---

## Result

**Mismatch due to INNER JOIN excluding authors without books**

**Key insight:**
Authors without any book associations (via book_author table) are excluded from the results. The fix requires using LEFT JOINs to preserve all authors from the base author table, with NULL values for computed metrics where no books exist.

**Authors missing (110 total):**
These are authors in the `author` table who have no entries in `book_author`, meaning they have no associated books in the database.
