# Column Mismatch Summary

## Database: ice_hockey_draft
## Table: players
## Column: NUM_GAMES_PLAYED

**Description:**
Number of games played by the player, replace NULL values with 0.

---

## Root Cause
**Wrong source column: SQL uses `sum_7yr_GP` from PlayerInfo (NHL games only) instead of `SUM(GP)` from SeasonStatus (all games)**

### Incorrect SQL Logic
```sql
player_info AS (
    SELECT
        ELITEID as elite_id,
        sum_7yr_GP as num_games_played
    FROM ICE_HOCKEY_DRAFT.AIRBYTE_SCHEMA.PLAYERINFO
)
-- Then: COALESCE(p.num_games_played, 0) as num_games_played
```

### Correct SQL Logic
```sql
games_played AS (
    SELECT
        ELITEID as elite_id,
        SUM(GP) as num_games_played
    FROM ICE_HOCKEY_DRAFT.AIRBYTE_SCHEMA.SEASONSTATUS
    GROUP BY ELITEID
)
-- Then: COALESCE(gp.num_games_played, 0) as num_games_played
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Total number of games played by the player across all seasons and leagues
  * This data is tracked in the `SeasonStatus` table with the `GP` column for each season record

* **What the SQL actually computes:**
  * Uses `sum_7yr_GP` from `PlayerInfo` table
  * This column specifically means "Total NHL games played in player's first 7 years of NHL career"
  * Most players in the draft data have 0 or very few NHL games, as they are draft prospects

**Schema evidence:**
- `PlayerInfo.sum_7yr_GP`: "Total NHL games played in players first 7 years of NHL career"
- `SeasonStatus.GP`: "number of games" (for each season record)

---

## Evidence

**Key comparison demonstrating the error:**

| Player ID | sum_7yr_GP (NHL only) | SUM(GP) from SeasonStatus | Ground Truth |
| --------- | --------------------- | ------------------------- | ------------ |
| 9 | 0 | 55 | 55 |
| 18 | 13 | 67 | 67 |
| 27 | 0 | 53 | 53 |
| 30 | 0 | 37 | 37 |
| 69 | 115 | 67 | 67 |

**Detailed example - Player 9:**
- sum_7yr_GP (PlayerInfo): 0 (no NHL games)
- GP records from SeasonStatus: [33, 7, 15] → SUM = 55
- Ground Truth: 55

**Impact:**
* Current implementation: **25/2171 matches (1.2%)**
* Corrected implementation: **2171/2171 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "number of games played" refers to all games across all seasons and leagues (tracked in SeasonStatus), not just NHL games in the first 7 years of a career (which is a specific metric in PlayerInfo). The SeasonStatus table contains the comprehensive game history needed for this calculation.
