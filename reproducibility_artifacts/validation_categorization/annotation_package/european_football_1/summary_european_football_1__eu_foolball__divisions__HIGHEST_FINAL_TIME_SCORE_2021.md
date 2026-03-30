# Column Mismatch Summary

## Database: european_football_1
## Table: eu_foolball__divisions
## Column: HIGHEST_FINAL_TIME_SCORE_2021

### Description
The highest final time score in the division in 2021.

---

## Root Cause
**Semantic misinterpretation: "Score" means goals by a single team, not total match goals**

### Incorrect SQL Logic
```sql
highest_score_2021 AS (
    SELECT
        div,
        MAX(fthg + ftag) AS highest_score
    FROM matchs_base
    WHERE season = 2021
    GROUP BY div
)
```

### Correct SQL Logic
```sql
highest_score_2021 AS (
    SELECT
        div,
        MAX(GREATEST(fthg, ftag)) AS highest_score
    FROM matchs_base
    WHERE season = 2021
    GROUP BY div
)
```

---

## Evidence
**Key comparison demonstrating the error:**

| Division | Wrong Logic (sum) | Correct Logic (max single) | Ground Truth |
| -------- | ----------------- | -------------------------- | ------------ |
| B1       | 10                | 7                          | 7.0          |
| D2       | 11                | 8                          | 8.0          |
| E1       | 9                 | 7                          | 7.0          |
| E3       | 9                 | 6                          | 6.0          |
| T1       | 9                 | 7                          | 7.0          |

**Example match showing the difference:**
- B1 division: Kortrijk vs Beerschot VA (2020-11-07) ended 5-5
  - Wrong calculation: 5 + 5 = 10 (total goals)
  - Correct calculation: MAX(5, 5) = 5 (highest single-team score that match)
  - The actual highest single-team score in B1 was 7 (e.g., Gent scoring 7 against Waregem)

**Impact:**
* Current implementation: **4/21 matches (19.0%)**
* Corrected implementation: **21/21 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The term "score" in football context refers to goals by ONE team, not the combined match total. The correct interpretation is `MAX(GREATEST(fthg, ftag))` - finding the highest goal count by any single team across all matches in the 2021 season.
