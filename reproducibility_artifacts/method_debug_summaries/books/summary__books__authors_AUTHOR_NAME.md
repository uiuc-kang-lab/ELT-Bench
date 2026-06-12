# Column Mismatch Summary

## Database: books
## Table: authors
## Column: AUTHOR_NAME

### Description
Name of the author.

---

## Root Cause
**Same as AUTHOR_ID: Missing 110 authors due to INNER JOIN filtering**

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
)
```

### Correct SQL Logic
```sql
-- Use LEFT JOINs to include all authors
SELECT
    a.author_id,
    a.author_name,
    ...
FROM author_data a
LEFT JOIN book_author_data ba ON a.author_id = ba.author_id
LEFT JOIN book_data b ON ba.book_id = b.book_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The name of every author should be present in the output.

* **What the SQL actually computes**: Same issue as AUTHOR_ID - INNER JOINs exclude authors without book associations.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total authors | 9237 | 9125 |
| Common authors name match | 9127/9127 | 100% |

**For authors present in both GT and Pred, names match 100%.**

The issue is purely about missing rows, not incorrect names.

**Impact:**
* Current implementation: **9125/9237 rows (98.8%)**
* Corrected implementation: **9237/9237 rows (100%)**

---

## Result

✅ **Names are correct for all authors present, but 110 authors are missing entirely**

**Key insight:**
This is the same root cause as AUTHOR_ID - the INNER JOIN excludes authors without books. The author_name values themselves are correctly populated when the author exists in the output.
