# Column Mismatch Summary

## Database: hockey
## Table: hockey__goalies
## Column: NUMBER_OF_SEASONS_PLAYED

### Description
The number of seasons the goalie has played, replace NULL values with 0.

---

## Root Cause
**Incorrect aggregation: Using COUNT(DISTINCT year) instead of COUNT(*) to count seasons/stints**

### Incorrect SQL Logic
```sql
goalies_aggregated AS (
    SELECT
        playerid,
        COUNT(DISTINCT year) AS number_of_seasons_played,
        ...
    FROM {{ source('airbyte_schema', 'goalies') }}
    GROUP BY playerid
)
```

### Correct SQL Logic
```sql
goalies_aggregated AS (
    SELECT
        playerid,
        COUNT(*) AS number_of_seasons_played,
        ...
    FROM {{ source('airbyte_schema', 'goalies') }}
    GROUP BY playerid
)
```

---

## Why the Original Logic Is Wrong

The current implementation uses `COUNT(DISTINCT year)` which counts the number of unique calendar years a goalie played. However, the ground truth counts total rows (stints) in the Goalies table, where each row represents a season/stint for a player.

**What the column description means:**
- "The number of seasons the goalie has played" - each stint with a team in a year counts as a separate season entry

**What the SQL actually computes:**
- Counts only distinct calendar years, ignoring that a player may have multiple stints (with different teams) in the same year

**Schema semantics from `source_schemas/Goalies.csv`:**
- `playerID`: id number identifying the player
- `year`: year of the season
- `stint`: order of appearance in a season (indicates multiple entries per year possible)
- `tmID`: team abbreviated name

The `stint` column indicates that players can have multiple entries per year when they play for different teams. Each row should be counted as a separate "season played."

---

## Evidence

**Key comparison demonstrating the error:**

| Player | COUNT(DISTINCT year) | COUNT(*) | Ground Truth |
| ------ | -------------------- | -------- | ------------ |
| aebisda01 | 7 | 8 | 8 |
| andercr01 | 9 | 10 | 10 |
| auldal01 | 10 | 12 | 12 |
| barrato01 | 19 | 22 | 22 |
| beaupdo01 | 17 | 19 | 19 |
| belfoed01 | 18 | 19 | 19 |

**Example player showing the difference (aebisda01):**
| Year | Stint | Team | GP | Min |
| ---- | ----- | ---- | -- | --- |
| 2000 | 1 | COL | 26 | 1393 |
| 2001 | 1 | COL | 21 | 1184 |
| 2002 | 1 | COL | 22 | 1235 |
| 2003 | 1 | COL | 62 | 3703 |
| 2005 | 1 | COL | 43 | 2477 |
| **2005** | **2** | **MTL** | **7** | **418** |
| 2006 | 1 | MTL | 32 | 1760 |
| 2007 | 1 | PHO | 1 | 60 |

- Wrong calculation: 7 distinct years (2000, 2001, 2002, 2003, 2005, 2006, 2007)
- Correct calculation: 8 total rows (including 2 stints in 2005)
- The player played for both COL and MTL in 2005, which counts as 2 seasons

**Impact:**
* Current implementation: **618/788 matches (78.4%)**
* Corrected implementation: **788/788 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The term "seasons played" in this context refers to total stints/appearances in the Goalies table, not unique calendar years. When a goalie is traded mid-season and plays for multiple teams in the same year, each team stint counts as a separate "season played."
