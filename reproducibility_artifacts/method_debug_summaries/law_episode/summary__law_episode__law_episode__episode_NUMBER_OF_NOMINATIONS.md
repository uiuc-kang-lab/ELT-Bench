# Column Mismatch Summary

## Database: law_episode
## Table: law_episode__episode
## Column: NUMBER_OF_NOMINATIONS

### Description
the number of nominations that the episode has, replace NULL values with 0.

---

## Root Cause
**Incorrect filter: Counting all awards (including wins) instead of only nominations**

### Incorrect SQL Logic
```sql
nomination_counts AS (
    SELECT
        EPISODE_ID,
        COUNT(*) AS number_of_nominations
    FROM {{ source('airbyte_schema', 'AWARD') }}
    WHERE EPISODE_ID IS NOT NULL
    GROUP BY EPISODE_ID
)
```

### Correct SQL Logic
```sql
nomination_counts AS (
    SELECT
        EPISODE_ID,
        COUNT(*) AS number_of_nominations
    FROM {{ source('airbyte_schema', 'AWARD') }}
    WHERE EPISODE_ID IS NOT NULL AND result = 'Nominee'
    GROUP BY EPISODE_ID
)
```

---

## Why the Original Logic Is Wrong

The current implementation counts ALL entries in the AWARD table for each episode, regardless of whether they are nominations or wins. The column is explicitly named "number_of_nominations" which should only count records where the episode was nominated (not where it won).

**What the column description means:**
- "the number of nominations that the episode has" = count only nomination records (result = 'Nominee')

**What the SQL actually computes:**
- Counts all award records (both 'Nominee' and 'Winner') for each episode

**Schema semantics from `source_schemas/Award.csv`:**
- `result`: the nomination result - can be 'Nominee' or 'Winner'
- A 'Winner' is not a nomination, it's an award that was won

---

## Evidence

**Key comparison demonstrating the error:**

| Episode | Wrong Logic (all awards) | Correct Logic (Nominee only) | Ground Truth |
| ------- | ------------------------ | ---------------------------- | ------------ |
| tt0629149 | 5 | 0 | 0 |
| tt0629228 | 3 | 0 | 0 |
| tt0629291 | 4 | 1 | 1 |
| tt0629397 | 1 | 0 | 0 |
| tt0629248 | 7 | 7 | 7 |

**Example episode showing the difference (tt0629149 - "Agony"):**
- Total awards: 5 (all are 'Winner')
- Nominations: 0 (none have result = 'Nominee')
- Wrong calculation: 5
- Correct calculation: 0
- Ground truth: 0

**Episode tt0629291 ("Hate") breakdown:**
- Nominee records: 1
- Winner records: 3
- Total: 4
- Wrong calculation: 4
- Correct calculation: 1
- Ground truth: 1

**Impact:**
* Current implementation: **20/24 matches (83.3%)**
* Corrected implementation: **24/24 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The AWARD table contains both nominations and wins. The column "number_of_nominations" should only count nomination records (where `result = 'Nominee'`), not all award records. Wins are outcomes of nominations, not nominations themselves.

**Episodes with nominations (result = 'Nominee'):**
- tt0629248 (Empire): 7 nominations
- tt0629291 (Hate): 1 nomination
- tt0629398 (Refuge: Part 2): 1 nomination
- tt0629422 (Sideshow): 1 nomination
