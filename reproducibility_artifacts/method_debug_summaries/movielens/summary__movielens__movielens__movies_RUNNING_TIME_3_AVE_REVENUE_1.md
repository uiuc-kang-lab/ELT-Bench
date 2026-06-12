# Column Mismatch Summary

## Database: movielens
## Table: movielens__movies
## Column: RUNNING_TIME_3_AVE_REVENUE_1

### Description
Set to 1 if the movie has a running time of 3 and an average revenue of 1, otherwise, set to 0

---

## Root Cause
**Wrong data source: "average revenue" refers to director's avg_revenue attribute, not movie's average rating**

### Incorrect SQL Logic
```sql
-- Calculate average revenue per movie (using rating as proxy for revenue)
movie_revenue AS (
    SELECT
        MOVIEID,
        AVG(rating) AS avg_revenue
    FROM u2base
    GROUP BY MOVIEID
)

-- Final SELECT
CASE
    WHEN m.RUNNINGTIME = 3 AND ROUND(COALESCE(rev.avg_revenue, 0)) = 1 THEN 1
    ELSE 0
END AS running_time_3_ave_revenue_1
```

### Correct SQL Logic
```sql
-- Join to get director's avg_revenue
CASE
    WHEN m.runningtime = 3 AND d.avg_revenue = 1 THEN 1
    ELSE 0
END AS running_time_3_ave_revenue_1
FROM movies m
LEFT JOIN movies2directors m2d ON m.movieid = m2d.movieid
LEFT JOIN directors d ON m2d.directorid = d.directorid
```

---

## Why the Original Logic Is Wrong

The movies table does not have a revenue column. The original implementation incorrectly assumed "average revenue" meant the average user rating from the `u2base` table. However, the ground truth uses the `avg_revenue` attribute from the `directors` table, which represents the director's average revenue across their filmography.

**What the column description means:**
- "average revenue of 1" = the movie's director has avg_revenue = 1 in the directors table

**What the SQL actually computes:**
- Average user rating rounded to 1 (which is extremely rare since ratings range 1-5 with avg ~3.5)

**Schema semantics from `source_schemas`:**
- `movies.runningtime`: Running time category (0-3)
- `directors.avg_revenue`: Average revenue of director's movies (0-4)
- `movies2directors`: Links movies to directors
- `u2base.rating`: Individual user ratings (1-5)

---

## Evidence

**Key comparison demonstrating the error:**

| Movie ID | Runtime | Avg Rating | Director Revenue | Wrong Flag | Correct Flag | Ground Truth |
| -------- | ------- | ---------- | ---------------- | ---------- | ------------ | ------------ |
| 1690377 | 3 | 3.5 | 1 | 0 | 1 | 1 |
| 1691793 | 3 | 3.2 | 1 | 0 | 1 | 1 |
| 1703679 | 3 | 4.0 | 1 | 0 | 1 | 1 |
| 1712152 | 3 | 3.8 | 1 | 0 | 1 | 1 |

**Data exploration:**
- Running time distribution: 0: 53, 1: 1221, 2: 1261, 3: 1297 movies
- Movies table columns: movieid, year, isEnglish, country, runningtime (no revenue!)
- Directors table columns: directorid, d_quality, avg_revenue

**Example showing the difference (Movie 1690377):**
- Running time: 3 (matches condition)
- Average user rating: ~3.5 (ROUND = 4, not 1)
- Director's avg_revenue: 1
- Wrong logic: runtime=3 AND round(avg_rating)=1 = FALSE
- Correct logic: runtime=3 AND director.avg_revenue=1 = TRUE
- Ground truth: 1

**Impact:**
* Current implementation: **3,709/3,832 matches (96.8%)**
* Corrected implementation: **3,832/3,832 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The "average revenue" in the column description refers to a director attribute (`directors.avg_revenue`), not a calculated average from user ratings. This is because the movies table has no revenue data - revenue information is only available at the director level. The correct implementation joins through `movies2directors` to access the director's `avg_revenue` attribute.

**Movies where RUNNING_TIME_3_AVE_REVENUE_1 = 1:**
Movies with runtime category 3 whose director has avg_revenue = 1 (123 movies total).
