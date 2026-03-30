# Column Mismatch Summary

## Database: video_games
## Table: publishers
## Column: PUBLISHED_ONLY_ONE_GAME

### Description (from data_model.yaml)
> Set to 1 if the publisher has published only one game, otherwise, set to 0.

---

## Root Cause
**This column is directly dependent on NUM_GAMES. Since NUM_GAMES has counting discrepancies due to the join logic issues, this boolean flag is also incorrect for affected publishers.**

### Predicted SQL Logic
```sql
CASE WHEN num_games = 1 THEN 1 ELSE 0 END AS published_only_one_game
```

### Correct SQL Logic
```sql
-- Same logic, but fix the underlying NUM_GAMES calculation first
CASE WHEN num_games = 1 THEN 1 ELSE 0 END AS published_only_one_game
```

---

## Why the Original Logic Is Wrong

* The CASE logic itself is correct (check if num_games = 1)
* The problem is inherited from the incorrect NUM_GAMES calculation
* When num_games is incorrectly calculated as 0 instead of 1, this flag becomes 0 instead of 1
* When num_games is incorrectly calculated as 1 instead of actual count, this flag becomes 1 instead of 0

---

## Evidence

**Sample Discrepancies:**

| Publisher | GT num_games | Predicted num_games | GT published_only_one | Predicted published_only_one |
|-----------|--------------|---------------------|----------------------|------------------------------|
| Magical Company | 1 | 0 | 1 | 0 |
| Nordcurrent | 5 | 1 | 0 | 1 |

**Impact Analysis:**
* When actual count = 1 but predicted = 0: Flag incorrectly shows 0 instead of 1
* When actual count > 1 but predicted = 1: Flag incorrectly shows 1 instead of 0
* Both false positives and false negatives are possible

---

## Result

**DEPENDENT COLUMN ERROR**: This column's mismatches are entirely caused by errors in the NUM_GAMES column calculation. The boolean logic (CASE WHEN num_games = 1) is correct, but it operates on incorrect input data.

**Key insight:**
Fix the NUM_GAMES calculation by reviewing the join logic (particularly the GAME_PLATFORM join), and this column will automatically be corrected. No changes needed to the PUBLISHED_ONLY_ONE_GAME logic itself - it correctly derives from num_games, the upstream value is just wrong.
