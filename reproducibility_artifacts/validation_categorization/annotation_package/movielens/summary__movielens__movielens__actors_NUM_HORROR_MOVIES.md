# Column Mismatch Summary

## Database: movielens
## Table: movielens__actors
## Column: NUM_HORROR_MOVIES

### Description
The number of horror movies the actor has acted in, replace NULL values with 0.

---

## Root Cause
**Aggregation issue: Should count rows (director-movie-genre entries), not distinct movies**

### Incorrect SQL Logic
```sql
-- Count horror movies per actor
horror_movies AS (
    SELECT
        m2a.actorid,
        COUNT(DISTINCT m2a.MOVIEID) AS num_horror_movies
    FROM movies2actors m2a
    JOIN movies2directors m2d ON m2a.MOVIEID = m2d.MOVIEID
    WHERE LOWER(m2d.GENRE) = 'horror'
    GROUP BY m2a.actorid
)
```

### Correct SQL Logic
```sql
-- Count horror entries per actor (rows, not distinct movies)
horror_movies AS (
    SELECT
        m2a.actorid,
        COUNT(*) AS num_horror_movies
    FROM movies2actors m2a
    JOIN movies2directors m2d ON m2a.MOVIEID = m2d.MOVIEID
    WHERE LOWER(m2d.GENRE) = 'horror'
    GROUP BY m2a.actorid
)
```

---

## Why the Original Logic Is Wrong

The `movies2directors` table contains multiple rows per movie when a movie has multiple directors. Each director-movie combination has its own genre entry. The ground truth counts the total number of horror genre entries (rows), not distinct horror movies.

**What the column description means:**
- "The number of horror movies" = count of horror genre entries in movies2directors

**What the SQL actually computes:**
- Count of distinct movies where at least one director has genre = 'Horror'

**Schema semantics from `source_schemas`:**
- `movies2directors`: Contains (movieid, directorid, genre) - one row per director-movie pair
- A single movie can have multiple directors, each with the same genre
- `movies2actors`: Links actors to movies

---

## Evidence

**Key comparison demonstrating the error:**

| Actor ID | Wrong Logic (DISTINCT movies) | Correct Logic (count rows) | Ground Truth |
| -------- | ----------------------------- | -------------------------- | ------------ |
| 1002370 | 1 | 2 | 2 |
| 1011170 | 1 | 2 | 2 |
| 1031965 | 1 | 2 | 2 |
| 1033040 | 1 | 2 | 2 |

**Example showing the difference (Actor 1002370):**
- Movies: 2485041 (Horror), 2452768 (Action)
- Movie 2485041 has 2 directors, both with genre='Horror':
  - (2485041, 113501, 'Horror')
  - (2485041, 201065, 'Horror')
- Wrong calculation: COUNT(DISTINCT movieid) = 1
- Correct calculation: COUNT(*) = 2
- Ground truth: 2

**Data structure:**
- movies2directors has multiple rows per movie when movie has multiple directors
- Each director entry duplicates the genre
- Total Horror entries in movies2directors: 231

**Impact:**
* Current implementation: **98,447/98,690 matches (99.8%)**
* Corrected implementation: **98,690/98,690 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The `movies2directors` table stores one row per director-movie pair, with each row containing the movie's genre. When a movie has multiple directors, the genre is repeated for each director entry. The ground truth counts these repeated entries (total rows), not the count of unique movies with Horror genre.
