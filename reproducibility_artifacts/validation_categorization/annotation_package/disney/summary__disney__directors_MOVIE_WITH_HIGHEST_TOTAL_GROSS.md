# Column Mismatch Summary

## Database: disney
## Table: directors
## Column: MOVIE_WITH_HIGHEST_TOTAL_GROSS

**Description:**
The movie with the highest total gross the director has directed, with ties broken by the descending order of the movie name

---

## Root Cause
**Join ambiguity error: SQL joins director movies to movies_total_gross by movie name without deduplication, causing animated films to match later remakes with the same name but different (often higher) gross values**

### Incorrect SQL Logic
```sql
director_movies AS (
    SELECT
        d.director_name,
        d.movie_name,
        m.total_gross
    FROM director_base d
    LEFT JOIN movies_gross m ON d.movie_name = m.MOVIE_TITLE
),

movie_with_highest_gross AS (
    SELECT
        director_name,
        movie_name AS movie_with_highest_total_gross,
        ROW_NUMBER() OVER (PARTITION BY director_name ORDER BY total_gross DESC, movie_name DESC) AS rn
    FROM director_movies
    WHERE total_gross IS NOT NULL
)
```

### Correct SQL Logic
```sql
-- Deduplicate movies_total_gross to use only the FIRST (oldest) entry for each movie name
movies_deduped AS (
    SELECT
        movie_title,
        total_gross,
        ROW_NUMBER() OVER (PARTITION BY movie_title ORDER BY release_date) AS rn
    FROM movies_total_gross
),

director_movies AS (
    SELECT
        d.director_name,
        d.movie_name,
        m.total_gross
    FROM director_base d
    LEFT JOIN movies_deduped m ON d.movie_name = m.movie_title AND m.rn = 1
),

movie_with_highest_gross AS (
    SELECT
        director_name,
        movie_name AS movie_with_highest_total_gross,
        ROW_NUMBER() OVER (PARTITION BY director_name ORDER BY total_gross DESC, movie_name DESC) AS rn
    FROM director_movies
    WHERE total_gross IS NOT NULL
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Find the movie with highest total_gross among all movies directed by each director
  * Each director in the director table directed ORIGINAL animated Disney films
  * The join should match to the ORIGINAL film's gross, not remakes

* **What the SQL actually computes:**
  * The SQL joins by movie name without considering release dates
  * Several movies have MULTIPLE entries in movies_total_gross (original + remakes):
    - "The Jungle Book": 1967 ($141M), 1994 ($44M), 2016 ($364M)
    - "101 Dalmatians": 1961 ($153M), 1996 ($136M)
    - "Cinderella": 1950 ($85M), 2015 ($201M)
    - "Alice in Wonderland": only 2010 entry ($334M) - 1951 animated version NOT in table
  * The JOIN picks an arbitrary entry (often the highest gross remake)
  * This causes Wolfgang Reitherman's "The Jungle Book" to get $364M (2016 remake) instead of $141M (1967 original)

**Schema verification:**
- `director.name`: "unique movie name" (refers to ORIGINAL animated films)
- `director.director`: "the name of the director"
- `movies_total_gross.movie_title`: "movie title" (includes originals AND remakes)

**Duplicate movie names in movies_total_gross:**
| Movie Title | Entries | Years | Gross Values |
| ----------- | ------- | ----- | ------------ |
| The Jungle Book | 3 | 1967, 1994, 2016 | $141M, $44M, $364M |
| 101 Dalmatians | 2 | 1961, 1996 | $153M, $136M |
| Cinderella | 2 | 1950, 2015 | $85M, $201M |
| Alice in Wonderland | 1 | 2010 only | $334M (1951 version missing) |

---

## Evidence

**Key comparison demonstrating the error:**

| Director | GT Movie | Pred Movie | GT Gross | Pred Gross | Issue |
| -------- | -------- | ---------- | -------- | ---------- | ----- |
| Clyde Geronimi | Sleeping Beauty | Alice in Wonderland | $9.5M | $334M | 1951 Alice not in table, joins to 2010 remake |
| Wolfgang Reitherman | The Aristocats | The Jungle Book | $55.7M | $364M | Joins to 2016 Jungle Book remake instead of 1967 |
| Ron Clements | Hercules | Moana | $99M | $246M | Multiple movies, wrong max selected |
| Gary Trousdale | Atlantis: The Lost Empire | Beauty and the Beast | $84M | $219M | Wrong max gross movie selected |
| Mark Dindal | The Emperor's New Groove | Chicken Little | $89M | $135M | Wrong max gross movie selected |
| Mike Gabriel | The Rescuers Down Under | Pocahontas | $28M | $142M | Wrong max gross movie selected |

**Example: Wolfgang Reitherman**
- Directed: 101 Dalmatians (1961), The Sword in the Stone (1963), The Jungle Book (1967), The Aristocats (1970), The Rescuers (1977)
- SQL finds "The Jungle Book" → joins to 2016 remake ($364M) instead of 1967 original ($141M)
- With wrong join, "The Jungle Book" appears highest
- GT shows "The Aristocats" suggesting correct original-only matching was used

**Impact:**
* Current implementation: **23/29 matches (79.3%)**
* Using first (oldest) movie entry: **23/29 matches (79.3%)** - still has 6 mismatches

---

## Result

**Partial match - 6 mismatches remain**

The analysis reveals two issues:

1. **Duplicate movie names**: The SQL joins animated director movies to later remakes with the same name but different gross values. This is clearly an error that should be fixed by deduplicating movies_total_gross to use only the first/oldest entry.

2. **Remaining mismatches**: Even after deduplication, 6 directors still don't match GT. This suggests either:
   - The GT was computed with additional filtering (e.g., only certain genres)
   - The GT has errors for these specific directors
   - There's additional context we're missing

**Directors affected by remake join issue:**
- Wolfgang Reitherman: "The Jungle Book" joins to 2016 remake ($364M vs $141M original)
- Wilfred Jackson: "Cinderella" joins to 2015 remake ($201M vs $85M original)

**Directors with unexplained GT values:**
- Clyde Geronimi: GT=Sleeping Beauty ($9.5M) but Alice in Wonderland 2010 = $334M
- Ron Clements: GT=Hercules ($99M) but Moana = $246M
- Gary Trousdale: GT=Atlantis ($84M) but Beauty and the Beast = $219M
