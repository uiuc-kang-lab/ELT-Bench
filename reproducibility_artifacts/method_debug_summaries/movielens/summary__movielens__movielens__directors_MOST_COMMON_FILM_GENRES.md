# Column Mismatch Summary

## Database: movielens
## Table: movielens__directors
## Column: MOST_COMMON_FILM_GENRES

### Description
The most common film genres directed by the director.

---

## Root Cause
**Missing tiebreaker: When multiple genres have the same count, alphabetical order should be used**

### Incorrect SQL Logic
```sql
-- Find most common genre per director
genre_counts AS (
    SELECT
        directorid,
        GENRE,
        COUNT(*) AS genre_count,
        ROW_NUMBER() OVER (PARTITION BY directorid ORDER BY COUNT(*) DESC) AS rn
    FROM movies2directors
    GROUP BY directorid, GENRE
),

most_common_genres AS (
    SELECT
        directorid,
        GENRE AS most_common_film_genres
    FROM genre_counts
    WHERE rn = 1
)
```

### Correct SQL Logic
```sql
-- Find most common genre per director with alphabetical tiebreaker
genre_counts AS (
    SELECT
        directorid,
        GENRE,
        COUNT(*) AS genre_count,
        ROW_NUMBER() OVER (PARTITION BY directorid ORDER BY COUNT(*) DESC, GENRE ASC) AS rn
    FROM movies2directors
    GROUP BY directorid, GENRE
),

most_common_genres AS (
    SELECT
        directorid,
        GENRE AS most_common_film_genres
    FROM genre_counts
    WHERE rn = 1
)
```

---

## Why the Original Logic Is Wrong

When a director has directed the same number of movies in multiple genres (a tie), the SQL needs a deterministic tiebreaker. The original SQL only orders by count descending, leaving the selection among tied genres non-deterministic. The ground truth uses alphabetical order as the tiebreaker.

**What the column description means:**
- "The most common film genres" = genre with highest count, alphabetical first if tied

**What the SQL actually computes:**
- Genre with highest count, with arbitrary selection among ties

**Schema semantics from `source_schemas`:**
- `movies2directors`: Contains (movieid, directorid, genre)
- Distinct genres: 'Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Horror', 'Other'

---

## Evidence

**Key comparison demonstrating the error:**

| Director ID | Wrong Logic (no tiebreaker) | Correct Logic (alphabetical) | Ground Truth |
| ----------- | --------------------------- | ---------------------------- | ------------ |
| 109378 | Drama | Comedy | Comedy |
| 112098 | Documentary | Crime | Crime |
| 114412 | Animation | Adventure | Adventure |
| 11566 | Other | Drama | Drama |
| 116837 | Documentary | Adventure | Adventure |

**Example showing the tiebreaker effect (Director 109378):**
- Comedy count: 2
- Drama count: 2
- Both tied at 2 movies
- Wrong logic: Selected 'Drama' (arbitrary/database-dependent)
- Correct logic: Selected 'Comedy' (alphabetically first)
- Ground truth: Comedy

**Impact:**
* Current implementation: **2,091/2,201 matches (95.0%)**
* Corrected implementation: **2,201/2,201 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
Adding `GENRE ASC` to the ORDER BY clause ensures deterministic selection when genre counts are tied. The alphabetical tiebreaker produces a 100% match with ground truth, confirming this is the expected behavior for resolving ties.
