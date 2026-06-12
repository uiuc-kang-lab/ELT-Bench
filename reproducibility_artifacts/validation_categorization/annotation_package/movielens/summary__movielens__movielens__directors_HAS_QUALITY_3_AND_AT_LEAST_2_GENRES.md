# Column Mismatch Summary

## Database: movielens
## Table: movielens__directors
## Column: HAS_QUALITY_3_AND_AT_LEAST_2_GENRES

### Description
Set to 1 if the director has a quality of at least 3 and has directed at least 2 genres, otherwise, set to 0

---

## Root Cause
**Semantic misinterpretation: "at least 2 genres" means >= 2 genre entries (rows), not >= 2 distinct genres**

### Incorrect SQL Logic
```sql
-- Count distinct genres per director
director_genre_count AS (
    SELECT
        directorid,
        COUNT(DISTINCT GENRE) AS num_genres
    FROM movies2directors
    GROUP BY directorid
)

-- Final condition
CASE
    WHEN d.d_quality >= 3 AND COALESCE(dgc.num_genres, 0) >= 2 THEN 1
    ELSE 0
END AS has_quality_3_and_at_least_2_genres
```

### Correct SQL Logic
```sql
-- Count genre entries (rows) per director
director_genre_count AS (
    SELECT
        directorid,
        COUNT(*) AS num_entries
    FROM movies2directors
    GROUP BY directorid
)

-- Final condition
CASE
    WHEN d.d_quality >= 3 AND COALESCE(dgc.num_entries, 0) >= 2 THEN 1
    ELSE 0
END AS has_quality_3_and_at_least_2_genres
```

---

## Why the Original Logic Is Wrong

The `movies2directors` table has one row per director-movie combination. The column description "at least 2 genres" is interpreted by the ground truth as having at least 2 entries (rows) in the movies2directors table, not at least 2 distinct genre values.

**What the column description means:**
- "at least 2 genres" = at least 2 genre entries (rows in movies2directors)

**What the SQL actually computes:**
- At least 2 unique/distinct genre values (e.g., must have both 'Action' and 'Comedy')

**Schema semantics from `source_schemas`:**
- `movies2directors`: Contains (movieid, directorid, genre) - one row per director-movie
- `directors`: Contains (directorid, d_quality, avg_revenue)

---

## Evidence

**Key comparison demonstrating the error:**

| Director ID | Quality | Distinct Genres | Total Entries | Wrong Flag | Correct Flag | Ground Truth |
| ----------- | ------- | --------------- | ------------- | ---------- | ------------ | ------------ |
| 101246 | 4 | 1 | 2 | 0 | 1 | 1 |
| 10238 | 4 | 1 | 2 | 0 | 1 | 1 |
| 10292 | 4 | 1 | 3 | 0 | 1 | 1 |
| 103096 | 3 | 1 | 2 | 0 | 1 | 1 |
| 104964 | 3 | 1 | 2 | 0 | 1 | 1 |

**Example showing the difference (Director 101246):**
- Quality: 4 (>= 3, meets first condition)
- Distinct genres: 1 (all movies are same genre)
- Total entries: 2 (directed 2 movies)
- Wrong logic: quality >= 3 AND distinct_genres >= 2 = FALSE
- Correct logic: quality >= 3 AND total_entries >= 2 = TRUE
- Ground truth: 1

**Statistics:**
- Directors with quality >= 3: 1,985
- Directors with >= 2 distinct genres: 518
- Directors with >= 2 entries: 720
- GT=1 count: 720

**Impact:**
* Current implementation: **1,989/2,201 matches (90.4%)**
* Corrected implementation: **2,201/2,201 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The phrase "at least 2 genres" in this context means "at least 2 genre entries" (rows in movies2directors), not "at least 2 different genre types". A director who has directed 2 movies both in 'Drama' would have 2 genre entries but only 1 distinct genre. The ground truth counts the former, not the latter.
