# Column Mismatch Summary

## Database: movies_4
## Table: movies4__movies
## Column: NUMBER_OF_MAIN_CHARACTERS

**Description:**
The number of main characters in the movie, replace NULL values with 0.

---

## Root Cause
**Wrong interpretation: SQL counts ALL cast members, but GT counts only cast_order=0 (protagonist/main character)**

### Incorrect SQL Logic
```sql
cast_count AS (
    SELECT
        MOVIE_ID,
        COUNT(*) AS number_of_main_characters
    FROM {{ source('airbyte_schema', 'movie_cast') }}
    GROUP BY MOVIE_ID
)
```

### Correct SQL Logic
```sql
cast_count AS (
    SELECT
        MOVIE_ID,
        COUNT(*) AS number_of_main_characters
    FROM {{ source('airbyte_schema', 'movie_cast') }}
    WHERE cast_order = 0  -- Only count the protagonist/main character
    GROUP BY MOVIE_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Main characters" refers to the protagonist or lead character, not all characters
  * In the movie_cast table, cast_order=0 indicates the main/lead character
  * Most movies have exactly 1 main character (cast_order=0)

* **What the SQL actually computes:**
  * Counts ALL rows in movie_cast for each movie
  * This gives the total number of cast members (including supporting roles, extras, etc.)
  * Values range from 2 to 100+ cast members per movie

* **Schema insight from movie_cast:**
  * cast_order column indicates billing order (0=lead, 1=second billing, etc.)
  * cast_order=0 represents the main/protagonist character
  * GT values are 0, 1, or 2, confirming it's counting main characters not all cast

---

## Evidence

**Key comparison demonstrating the error:**

| Movie ID | Title | Total Cast (Wrong) | cast_order=0 (Correct) | GT |
| -------- | ----- | ------------------ | ---------------------- | -- |
| 5 | Four Rooms | 24 | 1 | 1 |
| 11 | Star Wars | 106 | 1 | 1 |
| 12 | Finding Nemo | 24 | 1 | 1 |
| 13 | Forrest Gump | 66 | 1 | 1 |
| 22 | Pirates of the Caribbean | 19 | 1 | 1 |

**GT value distribution:**
```
NUMBER_OF_MAIN_CHARACTERS
1    2439 movies (most common - single protagonist)
0    2186 movies (no cast data)
2       2 movies (dual protagonists)
```

**Formula verification:**
- Movie 5 (Four Rooms): COUNT(*) = 24 cast members, COUNT(cast_order=0) = 1 main character
- Movie 11 (Star Wars): COUNT(*) = 106 cast members, COUNT(cast_order=0) = 1 main character
- This confirms "main character" means cast_order=0, not all cast

**Impact:**
* Current implementation: **2,186/4,627 matches (47.24%)** - only matches when COUNT(*)=GT by coincidence
* Corrected implementation: **4,614/4,627 matches (99.72%)**

---

## Result

**Near-perfect match with corrected logic (99.72%)**

**Key insight:**
The term "main characters" in movie context refers to the lead/protagonist role, not the entire cast. The movie_cast table uses cast_order to indicate billing order:
- cast_order = 0: Lead/protagonist (main character)
- cast_order = 1: Second billing
- cast_order = 2+: Supporting roles

Most movies have exactly 1 main character. The 13 remaining mismatches (0.28%) may be due to:
- Movies with no cast data in GT but cast data in movie_cast
- Data quality differences between source tables
