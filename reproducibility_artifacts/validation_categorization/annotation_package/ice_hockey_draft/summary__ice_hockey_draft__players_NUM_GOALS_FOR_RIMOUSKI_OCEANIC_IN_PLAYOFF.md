# Column Mismatch Summary

## Database: ice_hockey_draft
## Table: players
## Column: NUM_GOALS_FOR_RIMOUSKI_OCEANIC_IN_PLAYOFF

**Description:**
Number of goals scored by the player for the Rimouski Oceanic during the playoffs, replace NULL values with 0.

---

## Root Cause
**Wrong GAMETYPE value: SQL uses 'Pf' instead of 'Playoffs'**

### Incorrect SQL Logic
```sql
rimouski_playoff_goals AS (
    SELECT
        ELITEID,
        SUM(goals) as num_goals_for_Rimouski_Oceanic_in_playoff
    FROM season_status
    WHERE TEAM = 'Rimouski Oceanic' AND GAMETYPE = 'Pf'
    GROUP BY ELITEID
)
```

### Correct SQL Logic
```sql
rimouski_playoff_goals AS (
    SELECT
        ELITEID,
        SUM(G) as num_goals_for_Rimouski_Oceanic_in_playoff
    FROM SEASONSTATUS
    WHERE TEAM = 'Rimouski Oceanic' AND GAMETYPE = 'Playoffs'
    GROUP BY ELITEID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count playoff goals scored while playing for the team "Rimouski Oceanic"
  * GAMETYPE must be 'Playoffs' to identify playoff games

* **What the SQL actually computes:**
  * Uses `GAMETYPE = 'Pf'` which doesn't exist in the data
  * The actual playoff GAMETYPE value is 'Playoffs'
  * Result: Always returns 0 because no records match 'Pf'

**GAMETYPE values in SeasonStatus:**
- 'Regular Season' (4,062 records)
- 'Playoffs' (1,423 records)
- 'Pf' does NOT exist

**Note on team name:** There's a data quality issue with trailing space ("Rimouski Oceanic " vs "Rimouski Oceanic"), but using exact match 'Rimouski Oceanic' aligns with the ground truth.

---

## Evidence

**Key comparison demonstrating the error:**

| Player ID | Rimouski Playoff Goals | Wrong Logic | Correct Logic | Ground Truth |
| --------- | ---------------------- | ----------- | ------------- | ------------ |
| 3667 | 15 | 0 | 15 | 15 |
| 4723 | 4 | 0 | 4 | 4 |
| 8654 | 4 | 0 | 4 | 4 |
| 8946 | 1 | 0 | 1 | 1 |
| 9116 | 3 | 0 | 3 | 3 |

**Data verification for Player 3667:**
```
ELITEID   SEASON      TEAM              GAMETYPE        G
3667      1997-1998   Rimouski Oceanic  Regular Season  44
3667      1997-1998   Rimouski Oceanic  Playoffs        15
3667      1997-1998   Canada U20        Regular Season  1
```
- Wrong logic (GAMETYPE='Pf'): 0
- Correct logic (GAMETYPE='Playoffs'): 15
- Ground Truth: 15

**Impact:**
* Current implementation: **2158/2171 matches (99.4%)**
* Corrected implementation: **2171/2171 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that GAMETYPE values are full words ('Regular Season', 'Playoffs'), not abbreviations ('RS', 'Pf'). The SQL was using abbreviated values that don't exist in the actual data.

**Players who scored playoff goals for Rimouski Oceanic:**
- 13 players have recorded playoff goals for this team
- Goals range from 1 to 15 per player
