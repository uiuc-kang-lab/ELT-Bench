# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: NUM_REVIEWS_WITH_NEUTRAL_ATTITUDE

### Description
The number of reviews with a neutral attitude for the app, replace NULL values with 0.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore, missing apps without reviews**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    COALESCE(SUM(CASE WHEN SENTIMENT = 'Neutral' THEN 1 ELSE 0 END), 0) AS num_reviews_with_neutral_attitude
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
        COALESCE(SUM(CASE WHEN Sentiment = 'Neutral' THEN 1 ELSE 0 END), 0) AS num_reviews_with_neutral_attitude
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    COALESCE(r.num_reviews_with_neutral_attitude, 0) AS num_reviews_with_neutral_attitude
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count reviews with 'Neutral' sentiment for each app. Apps without reviews should have 0 for this count.

* **What the SQL actually computes**: The incorrect SQL only outputs apps present in `user_reviews`. Apps in the playstore without any reviews are excluded entirely instead of showing 0.

* **Schema semantics**:
  - `playstore`: Canonical list of all 9,659 apps
  - `user_reviews.Sentiment`: Can be 'Positive', 'Negative', 'Neutral', or NULL
  - 5,162 reviews have 'Neutral' sentiment

---

## Evidence
**Key comparison demonstrating the error:**

| App Category | Count | Wrong Output | Correct Output |
| ------------ | ----- | ------------ | -------------- |
| Apps with reviews | 1,074 | Included | Included |
| Apps without reviews | 8,585 | **Missing** | 0 |

**For apps that exist in both outputs:**
- The neutral counts match perfectly (1,020/1,020)
- The counting logic is correct

**Sentiment distribution in user_reviews:**

| Sentiment | Count |
| --------- | ----- |
| NaN/NULL | 26,861 |
| Positive | 23,992 |
| Negative | 8,271 |
| Neutral | 5,162 |

**Example apps:**

| App Name | Neutral Reviews | In Output? |
| -------- | --------------- | ---------- |
| 10 Best Foods for You | 22 | Yes (both) |
| BL IP-Camera | 0 | Missing in wrong query |
| Stolica.bg | 0 | Missing in wrong query |

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The description says "replace NULL values with 0" - this means apps with no reviews should show 0 neutral reviews, not be excluded from the output. The fix requires starting from the `playstore` table and LEFT JOINing with review statistics, then using COALESCE to convert NULL to 0.
