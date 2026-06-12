# Column Mismatch Summary

## Database: formula_1
## Table: formula__drivers
## Column: NUM_WINNINGS

### Description
The number of winnings by the driver, replace NULL values with 0.

---

## Root Cause
**SEMANTIC MISINTERPRETATION - "winnings" interpreted as race wins instead of total points**

### Incorrect SQL Logic
```sql
SELECT driverId, COUNT(*) AS num_winnings
FROM results WHERE position = '1'
GROUP BY driverId
```

### Correct SQL Logic
```sql
SELECT driverId, COALESCE(SUM(points), 0) AS num_winnings
FROM results
GROUP BY driverId
```

---

## Why the Original Logic Is Wrong

* The term "winnings" is ambiguous in racing context
* Predicted interprets as: count of race wins (position = 1)
* Ground Truth uses: total points accumulated (SUM of points)
* This is a domain knowledge gap - in F1, "winnings" typically refers to championship points

---

## Evidence

**Key comparison demonstrating the error:**

| Driver | GT Value | Predicted Value | Interpretation |
|--------|----------|-----------------|----------------|
| Lewis Hamilton | 542 | 60 | GT=points, Pred=wins |
| Nico Rosberg | 269 | 23 | GT=points, Pred=wins |
| Fernando Alonso | 346 | 32 | GT=points, Pred=wins |
| Michael Schumacher | 849 | 91 | GT=points, Pred=wins |

---

## Result

**Status**: SEMANTIC MISINTERPRETATION - Domain Knowledge

The column values are systematically different because "winnings" was interpreted as race victories (COUNT of position=1) instead of championship points (SUM of points).
