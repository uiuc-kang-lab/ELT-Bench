## Database: soccer_2016
## Table: teams
## Column: FIRST_MATCH_TIME

**Description:**
The time of the first match played by the team.

---

## Root Cause
**Row ordering mismatch - Ground truth uses string ordering of TEAM_ID, predicted uses numeric ordering**

### Incorrect SQL Logic
```sql
first_match AS (
    SELECT
        team_id,
        MIN(match_date) AS first_match_time
    FROM (
        SELECT CAST(TEAM_1 AS INTEGER) AS team_id, MATCH_DATE AS match_date
        FROM MATCH
        UNION ALL
        SELECT CAST(TEAM_2 AS INTEGER) AS team_id, MATCH_DATE AS match_date
        FROM MATCH
    ) AS all_team_matches
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

* The FIRST_MATCH_TIME calculation logic is correct:
  - Creates UNION ALL of all team participations (as TEAM_1 or TEAM_2)
  - Uses MIN(match_date) to find earliest match for each team
  - Correctly captures the first ever match played by each team
* All computed values match ground truth when compared by TEAM_ID
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Team ID | Team Name                   | Ground Truth   | Predicted      | Match? |
| ------- | --------------------------- | -------------- | -------------- | ------ |
| 1       | Kolkata Knight Riders       | 2008-04-18     | 2008-04-18     | Yes    |
| 2       | Royal Challengers Bangalore | 2008-04-18     | 2008-04-18     | Yes    |
| 3       | Chennai Super Kings         | 2008-04-19     | 2008-04-19     | Yes    |
| 9       | Kochi Tuskers Kerala        | 2011-04-09     | 2011-04-09     | Yes    |
| 11      | Sunrisers Hyderabad         | 2013-04-05     | 2013-04-05     | Yes    |
| 13      | Gujarat Lions               | 2016-04-11     | 2016-04-11     | Yes    |

*First match dates correctly reflect when each team entered the league*

**Impact:**
* Current implementation: **1/13 matches (7.7%)** (row-by-row comparison)
* Corrected implementation: **13/13 matches (100%)** (with consistent ordering)

---

## Result

**Row Ordering Issue - Match ground truth string-based ordering**

**Key insight:**
The FIRST_MATCH_TIME calculation is correct. The MIN(match_date) aggregation properly identifies each team's inaugural match. The comparison fails solely due to row ordering differences.
