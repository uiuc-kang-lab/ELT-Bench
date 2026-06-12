# Column Mismatch Summary

## Database: ice_hockey_draft
## Table: players
## Column: DIFF_GOALS_BEWTEEN_RS_AND_PF

**Description:**
the difference in the number of goals scored by the player during the regular season versus the playoffs

---

## Root Cause
**Two errors: (1) Wrong GAMETYPE values ('RS'/'Pf' instead of 'Regular Season'/'Playoffs'), and (2) Should return NULL when player has no playoffs records**

### Incorrect SQL Logic
```sql
goals_diff AS (
    SELECT
        ELITEID,
        SUM(CASE WHEN GAMETYPE = 'RS' THEN goals ELSE 0 END) as rs_goals,
        SUM(CASE WHEN GAMETYPE = 'Pf' THEN goals ELSE 0 END) as pf_goals,
        (SUM(CASE WHEN GAMETYPE = 'RS' THEN goals ELSE 0 END) -
         SUM(CASE WHEN GAMETYPE = 'Pf' THEN goals ELSE 0 END)) as diff_goals_bewteen_Rs_and_Pf
    FROM season_status
    GROUP BY ELITEID
)
```

### Correct SQL Logic
```sql
goals_diff AS (
    SELECT
        ELITEID,
        SUM(CASE WHEN GAMETYPE = 'Regular Season' THEN G ELSE 0 END) as rs_goals,
        SUM(CASE WHEN GAMETYPE = 'Playoffs' THEN G ELSE 0 END) as pf_goals,
        CASE
            WHEN SUM(CASE WHEN GAMETYPE = 'Playoffs' THEN 1 ELSE 0 END) > 0
            THEN SUM(CASE WHEN GAMETYPE = 'Regular Season' THEN G ELSE 0 END) -
                 SUM(CASE WHEN GAMETYPE = 'Playoffs' THEN G ELSE 0 END)
            ELSE NULL
        END as diff_goals_bewteen_Rs_and_Pf
    FROM SEASONSTATUS
    GROUP BY ELITEID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Difference in goals between regular season and playoffs
  * Should only be calculated for players who have BOTH regular season AND playoff records
  * Players without playoff records should have NULL (not 0)

* **What the SQL actually computes:**
  * Uses wrong GAMETYPE values: 'RS' and 'Pf' don't exist in the data
  * The actual values are 'Regular Season' and 'Playoffs'
  * Returns 0 for all players because the WHERE conditions never match

**GAMETYPE values in SeasonStatus:**
| GAMETYPE | Count |
| -------- | ----- |
| Regular Season | 4,062 |
| Playoffs | 1,423 |

---

## Evidence

**Key comparison demonstrating the error:**

| Player ID | RS Goals | Playoffs Goals | Wrong Logic | Correct Logic | Ground Truth |
| --------- | -------- | -------------- | ----------- | ------------- | ------------ |
| 9 | 9 | 0 (no records) | 0 | NULL | NULL |
| 18 | 22 | 4 | 0 | 18 | 18 |
| 27 | 15 | 0 (no records) | 0 | NULL | NULL |
| 69 | 51 | 14 | 0 | 37 | 37 |
| 89 | 22 | 0 (no records) | 0 | NULL | NULL |

**Player distribution:**
- Players with Regular Season records: 2,171
- Players with Playoffs records: 1,302
- Players with BOTH (get calculated value): 1,302
- Players with RS only (get NULL): 869

**Impact:**
* Current implementation: **45/2171 matches (2.1%)**
* Corrected implementation: **2171/2171 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insights are:
1. GAMETYPE values are 'Regular Season' and 'Playoffs', not 'RS' and 'Pf'
2. The difference should only be calculated for players who have playoff records
3. Players without playoff experience should have NULL, not 0
