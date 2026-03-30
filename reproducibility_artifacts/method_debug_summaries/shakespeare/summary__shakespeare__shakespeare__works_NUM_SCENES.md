# Column Mismatch Summary

## Database: shakespeare
## Table: shakespeare__works
## Column: NUM_SCENES

### Description
The number of scenes in the work, replace NULL values with 0.

---

## Root Cause
**Semantic misunderstanding: Scene numbers repeat across acts, so COUNT(DISTINCT Scene) undercounts**

### Incorrect SQL Logic
```sql
scene_counts AS (
    SELECT
        work_id,
        COUNT(DISTINCT Scene) as num_scenes
    FROM {{ source('airbyte_schema', 'chapters') }}
    GROUP BY work_id
)
```

### Correct SQL Logic
```sql
scene_counts AS (
    SELECT
        work_id,
        COUNT(*) as num_scenes
    FROM {{ source('airbyte_schema', 'chapters') }}
    GROUP BY work_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count the total number of scenes in the work
* **What the SQL actually computes**: Counts only the distinct Scene number values (1, 2, 3, etc.), ignoring that Scene numbers reset for each Act

In Shakespeare's plays, each chapter record represents a unique scene. The `Scene` column contains scene numbers within an act (Scene 1, Scene 2, etc.), which reset for each new act. Using `COUNT(DISTINCT Scene)` only counts how many unique scene numbers exist (typically 1-15), not the total number of scenes across all acts.

**Example - "Twelfth Night" (Work ID 1):**
- Has 5 acts with scenes numbered 1-5, 1-5, 1-4, 1-3, 1-1
- Total scenes: 5 + 5 + 4 + 3 + 1 = 18 scenes
- `COUNT(DISTINCT Scene)` returns only 5 (scene numbers 1,2,3,4,5)
- `COUNT(*)` returns 18 (total chapter records)

```
Act  Scene  Description
1    1      DUKE ORSINO's palace.
1    2      The sea-coast.
1    3      OLIVIA'S house.
1    4      DUKE ORSINO's palace.
1    5      OLIVIA'S house.
2    1      The sea-coast.        <-- Scene 1 repeats
2    2      A street.
...
```

---

## Evidence

**Key comparison demonstrating the error:**

| Work | Title | Wrong Logic (DISTINCT Scene) | Correct Logic (COUNT *) | Ground Truth |
| ---- | ----- | ---------------------------- | ----------------------- | ------------ |
| 1 | Twelfth Night | 5 | 18 | 18 |
| 2 | All's Well That Ends Well | 7 | 23 | 23 |
| 3 | Antony and Cleopatra | 15 | 42 | 42 |
| 4 | As You Like It | 7 | 22 | 22 |
| 5 | Comedy of Errors | 4 | 11 | 11 |
| 6 | Coriolanus | 10 | 28 | 28 |
| 8 | Hamlet | 7 | 20 | 20 |

**Impact:**
* Current implementation: **6/43 matches (14.0%)**
* Corrected implementation: **43/43 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
Each row in the `chapters` table represents one scene. The `Scene` column is just the scene number within an act (which resets each act), not a unique identifier. The correct approach is simply `COUNT(*)` to count all chapter/scene records.
