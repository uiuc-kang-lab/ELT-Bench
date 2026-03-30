# Column Mismatch Summary

## Database: movies_4
## Table: movies4__production_company
## Column: NUMBER_OF_MOVIES_RELEASED

**Description:**
The number of movies released by the production company, replace NULL values with 0.

---

## Root Cause
**INNER JOIN filters out movies that exist in movie_company but not in movie table**

### Incorrect SQL Logic
```sql
company_movies AS (
    SELECT
        mc.COMPANY_ID,
        m.MOVIE_ID,
        ...
    FROM {{ source('airbyte_schema', 'movie_company') }} mc
    INNER JOIN {{ source('airbyte_schema', 'movie') }} m ON mc.MOVIE_ID = m.MOVIE_ID
),

movie_count AS (
    SELECT
        COMPANY_ID,
        COUNT(DISTINCT MOVIE_ID) AS number_of_movies_released
    FROM company_movies
    GROUP BY COMPANY_ID
)
```

### Correct SQL Logic
```sql
movie_count AS (
    SELECT
        COMPANY_ID,
        COUNT(DISTINCT MOVIE_ID) AS number_of_movies_released
    FROM {{ source('airbyte_schema', 'movie_company') }}
    GROUP BY COMPANY_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count all movies associated with the production company in the movie_company table
  * This represents the company's full movie portfolio

* **What the SQL actually computes:**
  * Uses INNER JOIN with movie table, which filters out movies that exist in movie_company but not in movie table
  * There are 139 movie_ids in movie_company that don't exist in the movie table
  * These "orphan" movies are excluded from the count

* **Schema insight from movie_company:**
  * movie_company contains movie_id and company_id mappings
  * Some movie_ids in movie_company don't have corresponding records in the movie table
  * GT counts all movies from movie_company regardless of movie table existence

---

## Evidence

**Key comparison demonstrating the error:**

| Company | GT Count | Pred Count | Difference | Reason |
| ------- | -------- | ---------- | ---------- | ------ |
| Lucasfilm (1) | 15 | 14 | -1 | 1 movie not in movie table |
| Paramount (4) | 285 | 282 | -3 | 3 movies not in movie table |
| Columbia (5) | 201 | 198 | -3 | 3 movies not in movie table |
| New Line (12) | 165 | 162 | -3 | 3 movies not in movie table |
| Universal (33) | 311 | 302 | -9 | 9 movies not in movie table |

**Data verification for Lucasfilm (company_id=1):**
- movie_company has 15 distinct movie_ids: [11, 85, 87, 89, 217, 838, 1891, 1892, 1893, 1894, 1895, 10658, 12144, 72431, 333355]
- movie table is missing 1 movie (movie_id 333355)
- INNER JOIN produces count=14, direct count produces count=15

**Impact:**
* Current implementation: **4714/5047 matches (93.40%)**
* Corrected implementation: **5047/5047 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The movie_company table represents the authoritative source for production company-movie relationships. Some movies may exist in movie_company but not in the movie table (possibly deleted or not yet imported). The correct interpretation counts all movies from movie_company without filtering through the movie table.
