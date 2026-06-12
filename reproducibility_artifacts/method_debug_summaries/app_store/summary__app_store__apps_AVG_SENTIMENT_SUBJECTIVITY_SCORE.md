# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: AVG_SENTIMENT_SUBJECTIVITY_SCORE

### Description
The average sentiment subjectivity score of the app.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore, missing apps without reviews**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    AVG(SENTIMENT_SUBJECTIVITY) AS avg_sentiment_subjectivity_score
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
        AVG(Sentiment_Subjectivity) AS avg_sentiment_subjectivity_score
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    r.avg_sentiment_subjectivity_score
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Calculate the average sentiment subjectivity score for each app. Apps without reviews should have NULL for this metric (since there's no data to average).

* **What the SQL actually computes**: The incorrect SQL only outputs apps present in `user_reviews`. Apps in the playstore without any reviews are excluded entirely instead of showing NULL.

* **Schema semantics**:
  - `playstore`: Canonical list of all 9,659 apps
  - `user_reviews.Sentiment_Subjectivity`: Numerical score indicating how subjective/objective a review is
  - Apps without reviews should have NULL (not 0) since there's no meaningful average to compute

---

## Evidence
**Key comparison demonstrating the error:**

| App Category | Count | Wrong Output | Correct Output |
| ------------ | ----- | ------------ | -------------- |
| Apps with reviews | 1,074 | Included | Included |
| Apps without reviews | 8,585 | **Missing** | NULL |

**For apps that exist in both outputs:**
- The subjectivity scores match perfectly (1,020/1,020)
- The AVG() calculation is correct

**Sample apps missing from incorrect query:**

| App Name | In Playstore | In User Reviews | Expected Score |
| -------- | ------------ | --------------- | -------------- |
| BL IP-Camera | Yes | No | NULL |
| Stolica.bg | Yes | No | NULL |
| Chicken Invaders 3 | Yes | No | NULL |

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
Unlike count-based metrics, the average subjectivity score should be NULL (not 0) for apps without reviews, since averaging over no data points is undefined. The fix requires starting from the `playstore` table and LEFT JOINing with review statistics, preserving NULL values for apps without reviews.
