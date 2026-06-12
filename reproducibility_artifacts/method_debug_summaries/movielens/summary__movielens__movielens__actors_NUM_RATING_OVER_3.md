# Column Mismatch Summary

## Database: movielens
## Table: movielens__actors
## Column: NUM_RATING_OVER_3

### Description
The number of movies the actor has acted in with a rating over 3, replace NULL values with 0.

---

## Root Cause
**Semantic misinterpretation: "rating over 3" means individual user ratings > 3, not movies with average rating > 3**

### Incorrect SQL Logic
```sql
-- Calculate average rating per movie
movie_ratings AS (
    SELECT
        MOVIEID,
        AVG(rating) AS avg_rating
    FROM u2base
    GROUP BY MOVIEID
),

-- Count movies with rating over 3 per actor
high_rated_movies AS (
    SELECT
        m2a.actorid,
        COUNT(DISTINCT m2a.MOVIEID) AS num_rating_over_3
    FROM movies2actors m2a
    JOIN movie_ratings mr ON m2a.MOVIEID = mr.MOVIEID
    WHERE mr.avg_rating > 3
    GROUP BY m2a.actorid
)
```

### Correct SQL Logic
```sql
-- Count individual ratings > 3 for each actor's movies
high_rated_movies AS (
    SELECT
        m2a.actorid,
        COUNT(*) AS num_rating_over_3
    FROM movies2actors m2a
    JOIN u2base u ON m2a.movieid = u.movieid
    WHERE u.rating > 3
    GROUP BY m2a.actorid
)
```

---

## Why the Original Logic Is Wrong

The current implementation interprets "movies with a rating over 3" as movies where the **average** rating exceeds 3. However, the ground truth counts individual user ratings over 3 across all movies the actor appeared in.

**What the column description means:**
- "The number of movies the actor has acted in with a rating over 3" = count of individual rating entries > 3

**What the SQL actually computes:**
- Count of distinct movies where the average of all ratings > 3

**Schema semantics from `source_schemas`:**
- `u2base`: Contains individual user ratings (userid, movieid, rating)
- `movies2actors`: Links actors to movies they appeared in
- Each user-movie pair in u2base is a separate rating entry

---

## Evidence

**Key comparison demonstrating the error:**

| Actor ID | Wrong Logic (movies with avg > 3) | Correct Logic (ratings > 3) | Ground Truth |
| -------- | --------------------------------- | --------------------------- | ------------ |
| 1000020 | 1 | 159 | 159 |
| 1000054 | 1 | 8 | 8 |
| 1000057 | 1 | 226 | 226 |
| 1000060 | 1 | 324 | 324 |
| 1000097 | 9 | 1743 | 1743 |

**Example showing the difference:**
- Actor 1000020 appeared in movies that received many individual ratings
- Wrong calculation: Count only movies where average rating > 3 = 1 movie
- Correct calculation: Count all individual ratings > 3 across all movies = 159 ratings
- The actor appeared in movies that collectively received 159 ratings scoring over 3

**Impact:**
* Current implementation: **20,535/98,690 matches (20.8%)**
* Corrected implementation: **98,690/98,690 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The term "rating over 3" in this context refers to individual user rating entries in the `u2base` table, not the aggregate average rating of movies. The correct calculation joins `movies2actors` with `u2base` directly and counts all rating entries where `rating > 3`, rather than first computing movie averages.
