# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: NUM_NEGATIVE_COMMENTS

### Description
Number of negative comments for the app, replace NULL values with 0.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore, missing apps without reviews**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    COALESCE(SUM(CASE WHEN SENTIMENT = 'Negative' THEN 1 ELSE 0 END), 0) AS num_negative_comments
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
        COALESCE(SUM(CASE WHEN Sentiment = 'Negative' THEN 1 ELSE 0 END), 0) AS num_negative_comments
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    COALESCE(r.num_negative_comments, 0) AS num_negative_comments
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count the number of negative comments for each app, with 0 for apps that have no negative comments (including apps with no reviews at all).

* **What the SQL actually computes**: The incorrect SQL only outputs apps present in `user_reviews`. Apps in the playstore without any reviews are excluded entirely instead of showing 0.

* **Schema semantics**:
  - `playstore`: Canonical list of all 9,659 apps
  - `user_reviews.Sentiment`: Contains 'Positive', 'Negative', 'Neutral', or NULL values
  - Apps without reviews should have `num_negative_comments = 0`

---

## Evidence
**Key comparison demonstrating the error:**

| App Category | Count | Wrong Output | Correct Output |
| ------------ | ----- | ------------ | -------------- |
| Apps with reviews | 1,074 | Included | Included |
| Apps without reviews | 8,585 | **Missing** | 0 |

**For apps that exist in both outputs:**
- The negative comment counts match perfectly (1,020/1,020)
- The calculation logic is correct

**Sentiment distribution in user_reviews:**
| Sentiment | Count |
| --------- | ----- |
| NaN/NULL | 26,861 |
| Positive | 23,992 |
| Negative | 8,271 |
| Neutral | 5,162 |

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The description says "replace NULL values with 0" - this implies that apps with no reviews (which would have NULL for this metric) should show 0, not be excluded from the output entirely. The fix requires starting from the `playstore` table and LEFT JOINing with review statistics.
