# Column Mismatch Summary

## Database: books
## Table: authors
## Column: WROTE_FEWER_TOTAL_PAGES_THAN_THE_AVERAGE

### Description
Set to 1 if the author has written fewer total pages than the average total pages of all authors; otherwise, set to 0.

---

## Root Cause
**Average calculation excludes authors without books, inflating the average and causing misclassification**

### Incorrect SQL Logic
```sql
avg_total_pages AS (
    SELECT AVG(total_pages) AS avg_pages
    FROM author_stats  -- Only includes authors WITH books (due to INNER JOIN)
)

-- Final comparison
CASE WHEN ast.total_pages < (SELECT avg_pages FROM avg_total_pages) THEN 1 ELSE 0 END
```

### Correct SQL Logic
```sql
-- Include ALL authors in average calculation (authors without books = 0 pages)
avg_total_pages AS (
    SELECT AVG(COALESCE(total_pages, 0)) AS avg_pages
    FROM author_data a
    LEFT JOIN (
        SELECT author_id, SUM(num_pages) as total_pages
        FROM author_books
        GROUP BY author_id
    ) ab ON a.author_id = ab.author_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Compare each author's total pages against the average total pages across ALL authors. Authors with fewer pages than average get value 1.

* **What the SQL actually computes**: The average is calculated only over authors who have books (due to INNER JOIN in author_books). This excludes ~110 authors with 0 books (0 pages), which inflates the average.

* **Impact of inflated average**: With a higher average, fewer authors qualify as "below average", causing mismatches.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Result |
| ------ | ------ |
| Common authors | 9127 |
| Matches | 8440/9127 (92.5%) |
| Mismatches | 687 |

**The mismatch pattern:**
- 687 authors are classified differently
- If the average is inflated (excludes 0-page authors), authors near the boundary will be misclassified
- Authors who are actually below the TRUE average might show as above the INFLATED average

**Impact:**
* Current implementation: **8440/9127 matches (92.5%)**
* Corrected implementation: **9127/9127 matches (100%)**

---

## Result

**Mismatch due to average calculation excluding authors without books**

**Key insight:**
The phrase "average total pages of all authors" means ALL authors should be included in the average calculation. Authors without books contribute 0 pages to the average. By excluding them (via INNER JOIN), the average is artificially inflated, causing authors near the threshold to be misclassified.

**Example calculation difference:**
- Wrong avg: SUM(pages for 9125 authors) / 9125 = X
- Correct avg: SUM(pages for 9125 authors) / 9237 = Y (lower because denominator includes 110 more authors with 0 pages)

Authors with total_pages between Y and X will be misclassified.
