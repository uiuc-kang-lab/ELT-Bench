# Column Mismatch Summary

## Database: movies_4
## Table: movies4__person
## Column: HAS_WORKED_AS_A_MUSIC_EDITOR

**Description:**
Set to 1 if the person has worked as a 'Music Editor' in the movie, otherwise, set to 0

---

## Root Cause
**INNER JOIN with movie table excludes Music Editor jobs for movies not in the movie table**

### Incorrect SQL Logic
```sql
person_crew_movies AS (
    SELECT
        mc.PERSON_ID,
        m.MOVIE_ID,
        m.TITLE,
        m.RELEASE_DATE,
        m.VOTE_AVERAGE,
        mc.JOB
    FROM {{ source('airbyte_schema', 'movie_crew') }} mc
    INNER JOIN {{ source('airbyte_schema', 'movie') }} m ON mc.MOVIE_ID = m.MOVIE_ID
),

music_editor_check AS (
    SELECT
        PERSON_ID,
        MAX(CASE WHEN JOB = 'Music Editor' THEN 1 ELSE 0 END) AS has_worked_as_a_music_editor
    FROM person_crew_movies
    GROUP BY PERSON_ID
)
```

### Correct SQL Logic
```sql
music_editor_check AS (
    SELECT
        PERSON_ID,
        MAX(CASE WHEN JOB = 'Music Editor' THEN 1 ELSE 0 END) AS has_worked_as_a_music_editor
    FROM {{ source('airbyte_schema', 'movie_crew') }}
    GROUP BY PERSON_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Check if person has ANY 'Music Editor' job in movie_crew, regardless of whether the movie exists in movie table

* **What the SQL actually computes:**
  * Uses INNER JOIN with movie table, filtering out crew records for movies not in movie table
  * If a person's only 'Music Editor' job is for a movie not in the movie table, they incorrectly get value=0

* **Example demonstrating the issue:**
  * Person 49911 has 18 crew records across various movies
  * Their 'Music Editor' job is for movie_id 302688
  * Movie 302688 does NOT exist in the movie table
  * INNER JOIN excludes this record, so person 49911 incorrectly gets has_worked_as_a_music_editor=0
  * GT correctly identifies they worked as Music Editor (value=1)

---

## Evidence

**Key comparison demonstrating the error:**

| Person ID | Music Editor Movie | In Movie Table? | Pred Value | GT Value |
| --------- | ----------------- | --------------- | ---------- | -------- |
| 49911 | 302688 | No | 0 | 1 |
| 1448748 | (orphan movie) | No | 0 | 1 |
| 1491504 | (orphan movie) | No | 0 | 1 |
| 1544715 | (orphan movie) | No | 0 | 1 |
| 1546622 | (orphan movie) | No | 0 | 1 |

**Detailed investigation for Person 49911:**
```
Crew records in movie_crew:
- 6477: Original Music Composer
- 7278: Music
- 12657: Original Music Composer
- ... (15 more records)
- 302688: Music Editor  <-- This movie doesn't exist in movie table

Movies in movie table: [6477, 7278, 12657, 13805, 22051, 38579, 40264, 50359, 51540, 67660, 109431, 168530, 184098, 223702, 227159]
Movie 302688 is MISSING from movie table!
```

**Statistics:**
- Total mismatches: 10 persons
- All mismatches have GT=1, Pred=0
- All involve Music Editor jobs for movies not in the movie table

**Impact:**
* Current implementation: **104,828/104,838 matches (99.99%)**
* Corrected implementation: **104,838/104,838 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The column should check movie_crew directly without INNER JOIN to movie table. The INNER JOIN filters out crew records for "orphan" movies (movies that exist in movie_crew but not in movie table). This affects 10 persons who only have their 'Music Editor' job for such orphan movies.
