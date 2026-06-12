# Column Mismatch Summary

## Database: simpson_episodes
## Table: simpson_episodes__episode
## Column: STAR_7_CLASS

**Description:**
Set to 3 if the episode receives 7-star votes exceeding 1.1 times the season average. Set to 2 if the episode receives 7-star votes exceeding the season average but less than or equal to 1.1 times the average. Set to 1 if the episode receives 7-star votes that are at least 0.9 times the season average but do not exceed it. Otherwise, set to 0.

---

## Root Cause
**Incorrect threshold interpretation: SQL uses `> avg` for class 2, but GT uses `>= 0.9 * avg`**

### Incorrect SQL Logic
```sql
star_7_classification AS (
    SELECT
        s7.episode_id,
        CASE
            WHEN s7.star_7_votes > 1.1 * sa.avg_star_7_votes THEN 3
            WHEN s7.star_7_votes > sa.avg_star_7_votes AND s7.star_7_votes <= 1.1 * sa.avg_star_7_votes THEN 2
            WHEN s7.star_7_votes >= 0.9 * sa.avg_star_7_votes AND s7.star_7_votes <= sa.avg_star_7_votes THEN 1
            ELSE 0
        END AS star_7_class
    FROM star_7_votes s7
    LEFT JOIN season_avg_star_7 sa ON s7.season = sa.season
)
```

### Correct SQL Logic
```sql
star_7_classification AS (
    SELECT
        s7.episode_id,
        CASE
            WHEN s7.star_7_votes > 1.1 * sa.avg_star_7_votes THEN 3
            WHEN s7.star_7_votes >= 0.9 * sa.avg_star_7_votes THEN 2
            WHEN s7.star_7_votes >= 0.7 * sa.avg_star_7_votes THEN 1
            ELSE 0
        END AS star_7_class
    FROM star_7_votes s7
    LEFT JOIN season_avg_star_7 sa ON s7.season = sa.season
)
```

---

## Why the Original Logic Is Wrong

* **What the column description says**:
  - Class 3: votes > 1.1 * avg
  - Class 2: votes > avg AND votes <= 1.1 * avg
  - Class 1: votes >= 0.9 * avg AND votes <= avg
  - Class 0: votes < 0.9 * avg

* **What the GT actually implements**:
  - Class 3: votes > 1.1 * avg
  - Class 2: votes >= 0.9 * avg AND votes <= 1.1 * avg (i.e., "near the average")
  - Class 1: votes >= 0.7 * avg AND votes < 0.9 * avg
  - Class 0: votes < 0.7 * avg

The key difference is that class 2 in the GT includes ALL episodes that are within ±10% of the average (from 0.9× to 1.1× the average), not just those that "exceed" the average. This is a more inclusive definition of "near average" performance.

**Example - Season 20:**
- Season average: 250.48
- SQL interprets class 2 as: votes > 250.48 AND votes <= 275.52
- GT interprets class 2 as: votes >= 225.43 AND votes <= 275.52

For episode S20-E8 with 236 votes (ratio = 0.942):
- SQL: 236 < 250.48, so not "exceeding average" → Class 1
- GT: 236 >= 225.43 (0.9 × avg), so "near average" → Class 2

---

## Evidence

**Key comparison demonstrating the error:**

| Episode | 7-Star Votes | Ratio to Avg | Wrong Logic | Correct Logic | Ground Truth |
| ------- | ------------ | ------------ | ----------- | ------------- | ------------ |
| S20-E13 | 250 | 0.998 | 1 | 2 | 2 |
| S20-E8 | 236 | 0.942 | 1 | 2 | 2 |
| S20-E21 | 234 | 0.934 | 1 | 2 | 2 |
| S20-E14 | 202 | 0.806 | 0 | 1 | 1 |
| S20-E15 | 222 | 0.886 | 0 | 1 | 1 |
| S20-E5 | 221 | 0.882 | 0 | 1 | 1 |

**Season 20 thresholds:**
- Season average: 250.48
- 0.7 × avg = 175.33 (lower bound for class 1)
- 0.9 × avg = 225.43 (lower bound for class 2)
- 1.1 × avg = 275.52 (upper bound for class 2)

**Impact:**
* Current implementation: **15/21 matches (71.4%)**
* Corrected implementation: **21/21 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Classification with corrected thresholds:**
- Class 3 (> 1.1 × avg): S20-E1 (306), S20-E2 (301), S20-E16 (279), S20-E10 (278), S20-E6 (277), S20-E12 (276)
- Class 2 (0.9 to 1.1 × avg): S20-E3, S20-E4, S20-E11, S20-E18, S20-E7, S20-E17, S20-E19, S20-E13, S20-E8, S20-E21
- Class 1 (0.7 to 0.9 × avg): S20-E15 (222), S20-E5 (221), S20-E14 (202)
- Class 0 (< 0.7 × avg): S20-E20 (163), S20-E9 (154)

