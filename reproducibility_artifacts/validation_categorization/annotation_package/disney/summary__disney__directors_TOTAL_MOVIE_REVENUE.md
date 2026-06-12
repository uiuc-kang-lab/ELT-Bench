# Column Mismatch Summary

## Database: disney
## Table: directors
## Column: TOTAL_MOVIE_REVENUE

**Description:**
The total revenue of the movies the director has directed, replace NULL values with 0.

---

## Root Cause
**Semantic error: SQL joins to the revenue table (Disney company annual revenue) instead of using total_gross from movies_total_gross table (actual movie box office revenue)**

### Incorrect SQL Logic
```sql
director_revenue AS (
    SELECT
        d.director_name,
        COALESCE(SUM(r.revenue), 0) AS total_movie_revenue
    FROM director_base d
    LEFT JOIN movies_gross m ON d.movie_name = m.MOVIE_TITLE
    LEFT JOIN revenue_data r ON m.release_year = r.YEAR
    GROUP BY d.director_name
)
```

### Correct SQL Logic
```sql
director_revenue AS (
    SELECT
        d.director_name,
        COALESCE(SUM(
            CAST(REPLACE(REPLACE(m.TOTAL_GROSS, '$', ''), ',', '') AS NUMBER)
        ), 0) AS total_movie_revenue
    FROM director_base d
    LEFT JOIN movies_gross m ON d.movie_name = m.MOVIE_TITLE
    GROUP BY d.director_name
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Total revenue of the movies" = sum of box office gross for all movies directed by each director
  * The movies_total_gross table contains actual movie revenue in the `total_gross` column

* **What the SQL actually computes:**
  * The SQL joins to the `revenue` table by movie release year
  * The `revenue` table contains **Disney company annual segment revenue** (in millions), NOT individual movie revenue
  * For example, the revenue table has entries like "1998: $22,976" which represents Disney's total company revenue for 1998
  * This is fundamentally different from individual movie gross

**Schema verification:**
- `movies_total_gross.total_gross`: "The total gross of the movie" (e.g., "$120,620,254")
- `revenue.total`: "The total box office gross for the movie" (MISLEADING - this is actually Disney company annual revenue in millions)

**Data comparison:**
| Source | Example Value | Unit | Description |
| ------ | ------------- | ---- | ----------- |
| movies_total_gross.total_gross | $120,620,254 | dollars | Movie box office gross |
| revenue.total | 22,976 | millions | Disney company annual revenue |

---

## Evidence

**Key comparison demonstrating the error:**

| Director | Wrong Logic (revenue table) | Correct Logic (movies_total_gross) | Ground Truth |
| -------- | --------------------------- | ---------------------------------- | ------------ |
| Art Stevens | 0 | 43,899,231 | 43,899,231 |
| Barry Cook | 22,976 | 120,620,254 | 120,620,254 |
| Byron Howard | 55,632 | 341,268,248 | 341,268,248 |
| Chris Buck | 68,443 | 571,829,828 | 571,829,828 |
| Ron Clements | 147,116 | 840,214,815 | 840,214,815 |
| Wolfgang Reitherman | 84,785 | 966,009,582 | 966,009,582 |

**Example calculation for Barry Cook (directed Mulan):**
- Wrong: Mulan released in 1998, revenue table has 1998 total = 22,976 (million)
- Correct: Mulan's total_gross from movies_total_gross = $120,620,254
- GT = 120,620,254

**Impact:**
* Current implementation: **2/29 matches (6.9%)**
* Corrected implementation: **29/29 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that the `revenue` table contains Disney company-wide annual segment revenue (in millions), NOT individual movie box office gross. The column description says "total revenue of the movies" which means the sum of actual movie gross values from the `movies_total_gross.total_gross` column.

**Sample directors with total movie revenue:**
- Wolfgang Reitherman: $966,009,582 (highest - 7 movies including The Jungle Book, 101 Dalmatians)
- Ron Clements: $840,214,815 (7 movies including Aladdin, The Little Mermaid, Moana)
- Chris Buck: $571,829,828 (2 movies: Frozen, Tarzan)
- Roger Allers: $422,780,140 (1 movie: The Lion King)
