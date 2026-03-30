## Database: soccer_2016
## Table: teams
## Column: WIN_RATE

**Description:**
The win rate of the team.

---

## Root Cause
**Scaling issue - Predicted returns decimal (0-1), ground truth expects percentage (0-100). Additionally, row ordering differs.**

### Incorrect SQL Logic
```sql
CASE
    WHEN tm.total_matches > 0 THEN COALESCE(w.total_wins, 0)::FLOAT / tm.total_matches
    ELSE 0
END AS win_rate
-- Returns decimal: 0.5151515151515151
```

### Correct SQL Logic
```sql
CASE
    WHEN tm.total_matches > 0 THEN COALESCE(w.total_wins, 0)::FLOAT / tm.total_matches * 100
    ELSE 0
END AS win_rate
-- Returns percentage: 51.515151515151516
-- Plus ORDER BY CAST(t.team_id AS VARCHAR) ASC for consistent ordering
```

---

## Why the Original Logic Is Wrong

* The win rate formula calculates wins/total_matches correctly
* However, ground truth stores win_rate as a **percentage** (0-100)
* Predicted stores win_rate as a **decimal** (0-1)
* Missing multiplication by 100 causes all values to be 100x smaller
* Additionally, row ordering differs (string vs numeric TEAM_ID ordering)

---

## Evidence

**Key comparison demonstrating the error:**

| Team ID | Team Name                   | Ground Truth       | Predicted          | Ratio |
| ------- | --------------------------- | ------------------ | ------------------ | ----- |
| 1       | Kolkata Knight Riders       | 51.515151515151516 | 0.5151515151515151 | 100x  |
| 2       | Royal Challengers Bangalore | 50.35971223021583  | 0.5035971223021583 | 100x  |
| 3       | Chennai Super Kings         | 60.30534351145038  | 0.6030534351145038 | 100x  |
| 7       | Mumbai Indians              | 57.142857142857146 | 0.5714285714285714 | 100x  |
| 10      | Pune Warriors               | 26.08695652173913  | 0.2608695652173913 | 100x  |
| 13      | Gujarat Lions               | 56.25              | 0.5625             | 100x  |

*All predicted values are exactly 100x smaller than ground truth*

**Impact:**
* Current implementation: **0/13 matches (0%)**
* Corrected implementation: **13/13 matches (100%)** (with *100 and consistent ordering)

---

## Result

**Scaling Issue - Multiply win_rate by 100 and fix row ordering**

**Key insight:**
The WIN_RATE column has two issues:
1. **Scaling**: Multiply the ratio by 100 to convert from decimal to percentage
2. **Ordering**: Use string-based ordering of TEAM_ID to match ground truth

The underlying win/loss calculation is correct - only the output format needs adjustment.
