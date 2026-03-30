## Database: soccer_2016
## Table: teams
## Column: NUMBER_OF_LOSSES

**Description:**
The number of matches the team has lost, replace NULL values with 0.

---

## Root Cause
**Row ordering mismatch - Ground truth uses string ordering of TEAM_ID, predicted uses numeric ordering**

### Incorrect SQL Logic
```sql
losses AS (
    SELECT
        team_id,
        COUNT(*) AS number_of_losses
    FROM (
        SELECT CAST(TEAM_1 AS INTEGER) AS team_id, CAST(MATCH_WINNER AS INTEGER) AS winner
        FROM MATCH WHERE MATCH_WINNER IS NOT NULL
        UNION ALL
        SELECT CAST(TEAM_2 AS INTEGER) AS team_id, CAST(MATCH_WINNER AS INTEGER) AS winner
        FROM MATCH WHERE MATCH_WINNER IS NOT NULL
    ) AS all_matches
    WHERE team_id != winner
    GROUP BY team_id
)
-- Results returned without consistent ORDER BY
```

### Correct SQL Logic
```sql
-- Same logic, but final SELECT includes:
ORDER BY CAST(t.team_id AS VARCHAR) ASC  -- String ordering to match ground truth
```

---

## Why the Original Logic Is Wrong

* The NUMBER_OF_LOSSES calculation logic is correct:
  - Creates UNION ALL of all team participations (as TEAM_1 or TEAM_2)
  - Counts matches where team participated but was not the winner
  - Correctly excludes ties/no-results by filtering MATCH_WINNER IS NOT NULL
  - COALESCE handles teams with no losses
* All computed values match ground truth when compared by TEAM_ID
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Team ID | Team Name                   | Ground Truth | Predicted | Match? |
| ------- | --------------------------- | ------------ | --------- | ------ |
| 1       | Kolkata Knight Riders       | 64           | 64        | Yes    |
| 2       | Royal Challengers Bangalore | 67           | 67        | Yes    |
| 3       | Chennai Super Kings         | 52           | 52        | Yes    |
| 6       | Delhi Daredevils            | 75           | 75        | Yes    |
| 10      | Pune Warriors               | 33           | 33        | Yes    |

*All loss counts match exactly when compared by TEAM_ID key*

**Impact:**
* Current implementation: **1/13 matches (7.7%)** (row-by-row comparison)
* Corrected implementation: **13/13 matches (100%)** (with consistent ordering)

---

## Result

**Row Ordering Issue - Match ground truth string-based ordering**

**Key insight:**
The NUMBER_OF_LOSSES calculation is correct. The UNION ALL approach properly captures all match participations and counts losses (where team played but didn't win). The comparison fails solely due to row ordering.
