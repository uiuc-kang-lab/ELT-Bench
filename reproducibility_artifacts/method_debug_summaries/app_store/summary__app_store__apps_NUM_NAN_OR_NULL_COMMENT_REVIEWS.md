# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: NUM_NAN_OR_NULL_COMMENT_REVIEWS

### Description
The number of reviews the app received whose comment is 'nan' or null, replace NULL values with 0.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore, missing apps without reviews**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    COALESCE(SUM(CASE WHEN TRANSLATED_REVIEW IS NULL OR LOWER(TRANSLATED_REVIEW) = 'nan' THEN 1 ELSE 0 END), 0) AS num_nan_or_null_comment_reviews
FROM user_reviews
GROUP BY APP
```

### Correct SQL Logic
```sql
WITH playstore_apps AS (
    SELECT DISTINCT App as app_name
    FROM playstore
),
review_stats AS (
    SELECT
        App as app_name,
        COALESCE(SUM(CASE WHEN Translated_Review IS NULL OR LOWER(CAST(Translated_Review AS TEXT)) = 'nan' THEN 1 ELSE 0 END), 0) AS num_nan_or_null_comment_reviews
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    COALESCE(r.num_nan_or_null_comment_reviews, 0) AS num_nan_or_null_comment_reviews
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count reviews where the translated comment is either NULL or the literal string 'nan'. Apps without any reviews should have 0 for this count.

* **What the SQL actually computes**: The incorrect SQL only outputs apps present in `user_reviews`. Apps in the playstore without any reviews are excluded entirely instead of showing 0.

* **Schema semantics**:
  - `playstore`: Canonical list of all 9,659 apps
  - `user_reviews.Translated_Review`: The preprocessed and translated review text; can be NULL or literal 'nan' string
  - 26,866 reviews have NULL/nan values for Translated_Review

---

## Evidence
**Key comparison demonstrating the error:**

| App Category | Count | Wrong Output | Correct Output |
| ------------ | ----- | ------------ | -------------- |
| Apps with reviews | 1,074 | Included | Included |
| Apps without reviews | 8,585 | **Missing** | 0 |

**For apps that exist in both outputs:**
- The nan/null counts match perfectly (1,020/1,020)
- The counting logic is correct

**Review data exploration:**

| Metric | Count |
| ------ | ----- |
| Total reviews | 64,286 |
| NULL Translated_Review | 26,866 |
| 'nan' string reviews | 26,866 |

Note: The NULL and 'nan' counts are identical, indicating that pandas likely converted NULL to 'nan' string during CSV loading.

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The description says "replace NULL values with 0" - this means apps with no reviews should show 0, not be excluded. The fix requires starting from the `playstore` table and LEFT JOINing with review statistics, then using COALESCE to convert NULL to 0.
