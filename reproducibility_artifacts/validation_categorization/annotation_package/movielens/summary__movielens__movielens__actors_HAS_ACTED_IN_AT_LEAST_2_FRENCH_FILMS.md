# Column Mismatch Summary

## Database: movielens
## Table: movielens__actors
## Column: HAS_ACTED_IN_AT_LEAST_2_FRENCH_FILMS

### Description
Set to 1 if the actor has acted in at least 2 French films, otherwise, set to 0

---

## Root Cause
**Two issues: (1) Wrong country value 'french' instead of 'France', and (2) Threshold should be > 2 not >= 2**

### Incorrect SQL Logic
```sql
-- Count French films per actor
french_films AS (
    SELECT
        m2a.actorid,
        COUNT(DISTINCT m2a.MOVIEID) AS num_french_films
    FROM movies2actors m2a
    JOIN movies m ON m2a.MOVIEID = m.MOVIEID
    WHERE LOWER(m.COUNTRY) = 'french'
    GROUP BY m2a.actorid
)

-- Final SELECT
CASE
    WHEN COALESCE(ff.num_french_films, 0) >= 2 THEN 1
    ELSE 0
END AS has_acted_in_at_least_2_French_films
```

### Correct SQL Logic
```sql
-- Count French films per actor
french_films AS (
    SELECT
        m2a.actorid,
        COUNT(DISTINCT m2a.MOVIEID) AS num_french_films
    FROM movies2actors m2a
    JOIN movies m ON m2a.MOVIEID = m.MOVIEID
    WHERE m.COUNTRY = 'France'
    GROUP BY m2a.actorid
)

-- Final SELECT
CASE
    WHEN COALESCE(ff.num_french_films, 0) > 2 THEN 1
    ELSE 0
END AS has_acted_in_at_least_2_French_films
```

---

## Why the Original Logic Is Wrong

The current implementation has two issues:

1. **Country value mismatch**: The SQL filters on `LOWER(country) = 'french'` but the actual data contains `'France'` as the country value. The lowercase 'french' is a language/adjective, not the country name stored in the data.

2. **Threshold ambiguity**: Despite the description saying "at least 2", the ground truth uses `> 2` (more than 2, i.e., 3 or more). This is a semantic discrepancy between the description and the actual implementation.

**What the column description means:**
- "at least 2 French films" = actors who appeared in 2 or more French films

**What the SQL actually computes:**
- Actors who appeared in movies where country = 'french' (which matches 0 movies)

**Schema semantics from `source_schemas`:**
- `movies.country`: Contains country names like 'France', 'UK', 'USA', 'other'
- `movies2actors`: Links actors to movies

---

## Evidence

**Key comparison demonstrating the error:**

| Actor ID | Wrong Logic (>= 2, 'french') | Correct Logic (> 2, 'France') | Ground Truth |
| -------- | ---------------------------- | ----------------------------- | ------------ |
| 1002887 | 0 | 0 | 0 |
| 1005653 | 0 | 0 | 0 |
| 1011828 | 0 | 0 | 0 |
| 1002246 | 0 | 1 | 1 |

**Data exploration:**
- Movies with country='french': 0
- Movies with country='France': 192
- Distinct countries in database: ['France', 'UK', 'USA', 'other']

**Threshold analysis:**
- Using >= 2 with 'France': 98,324/98,690 matches (366 overcounted)
- Using > 2 with 'France': 98,690/98,690 matches (100%)

**Impact:**
* Current implementation: **98,573/98,690 matches (99.9%)**
* Corrected implementation: **98,690/98,690 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The country filter must use the exact value stored in the database ('France', not 'french'). Additionally, the threshold "> 2" (more than 2) produces a perfect match rather than ">= 2" (at least 2), indicating a discrepancy between the column description and the actual ground truth logic.
