# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: PER_RATIO_BETWEEN_POSITIVE_AND_NEGATIVE_SETIMENTS

### Description
The percentage ratio between positive and negative sentiments for the app.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore, missing apps without reviews**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    CASE
        WHEN SUM(CASE WHEN SENTIMENT = 'Negative' THEN 1 ELSE 0 END) = 0 THEN NULL
        ELSE (SUM(CASE WHEN SENTIMENT = 'Positive' THEN 1 ELSE 0 END) * 100.0) / SUM(CASE WHEN SENTIMENT = 'Negative' THEN 1 ELSE 0 END)
    END AS per_ratio_between_positive_and_negative_setiments
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
        CASE
            WHEN SUM(CASE WHEN Sentiment = 'Negative' THEN 1 ELSE 0 END) = 0 THEN NULL
            ELSE (SUM(CASE WHEN Sentiment = 'Positive' THEN 1 ELSE 0 END) * 100.0) / SUM(CASE WHEN Sentiment = 'Negative' THEN 1 ELSE 0 END)
        END AS per_ratio_between_positive_and_negative_setiments
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    r.per_ratio_between_positive_and_negative_setiments
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Calculate the percentage ratio of positive to negative sentiments. Formula: `(positive_count * 100) / negative_count`. Apps without reviews or without negative reviews should have NULL.

* **What the SQL actually computes**: The incorrect SQL only outputs apps present in `user_reviews`. Apps in the playstore without any reviews are excluded entirely instead of showing NULL.

* **Schema semantics**:
  - `playstore`: Canonical list of all 9,659 apps
  - `user_reviews.Sentiment`: 'Positive', 'Negative', 'Neutral', or NULL
  - Ratio = (Positive Count / Negative Count) * 100
  - NULL when no negative reviews (division by zero protection)

---

## Evidence
**Key comparison demonstrating the error:**

| App Category | Count | Wrong Output | Correct Output |
| ------------ | ----- | ------------ | -------------- |
| Apps with reviews | 1,074 | Included | Included |
| Apps without reviews | 8,585 | **Missing** | NULL |

**For apps that exist in both outputs:**
- The ratio values match perfectly (1,020/1,020)
- The calculation logic is correct

**Example ratio calculations:**

| App Name | Positive | Negative | Ratio |
| -------- | -------- | -------- | ----- |
| 10 Best Foods for You | 162 | 10 | 1620.0% |
| 11st | 23 | 7 | 328.57% |
| 8 Ball Pool | 104 | 106 | 98.11% |
| 365Scores - Live Scores | 2 | 0 | NULL |

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The ratio should be NULL for apps without reviews (no data) or apps without negative reviews (division by zero). The fix requires starting from the `playstore` table and LEFT JOINing with review statistics, preserving NULL values appropriately.
