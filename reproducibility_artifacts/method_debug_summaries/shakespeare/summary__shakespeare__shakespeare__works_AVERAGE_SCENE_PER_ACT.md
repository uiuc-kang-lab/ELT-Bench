# Column Mismatch Summary

## Database: shakespeare
## Table: shakespeare__works
## Column: AVERAGE_SCENE_PER_ACT

### Description
The average number of scenes per act in the work.

---

## Root Cause
**Derived error: Uses incorrect NUM_SCENES calculation (COUNT DISTINCT Scene instead of COUNT *)**

### Incorrect SQL Logic
```sql
act_info AS (
    SELECT
        work_id,
        COUNT(DISTINCT Act) as num_acts,
        COUNT(DISTINCT Scene) as num_scenes  -- Wrong: Scene numbers repeat across Acts
    FROM {{ source('airbyte_schema', 'chapters') }}
    GROUP BY work_id
)

SELECT
    ...
    CASE
        WHEN ai.num_acts > 0 THEN ai.num_scenes::FLOAT / ai.num_acts::FLOAT
        ELSE 0
    END as average_scene_per_act
```

### Correct SQL Logic
```sql
act_info AS (
    SELECT
        work_id,
        COUNT(DISTINCT Act) as num_acts,
        COUNT(*) as num_scenes  -- Correct: Count all scene records
    FROM {{ source('airbyte_schema', 'chapters') }}
    GROUP BY work_id
)

SELECT
    ...
    CASE
        WHEN ai.num_acts > 0 THEN ai.num_scenes::FLOAT / ai.num_acts::FLOAT
        ELSE 0
    END as average_scene_per_act
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Total scenes divided by total acts = average scenes per act
* **What the SQL actually computes**: Distinct scene numbers divided by distinct acts

This error is a direct consequence of the NUM_SCENES error. The formula `num_scenes / num_acts` is correct, but `num_scenes` is calculated incorrectly using `COUNT(DISTINCT Scene)` instead of `COUNT(*)`.

**Example - "Twelfth Night":**
- 5 acts, 18 total scenes
- Correct average: 18 / 5 = 3.6 scenes per act
- Wrong average: 5 / 5 = 1.0 (using COUNT DISTINCT Scene = 5)

---

## Evidence

**Key comparison demonstrating the error:**

| Work | Title | Wrong Logic | Correct Logic | Ground Truth |
| ---- | ----- | ----------- | ------------- | ------------ |
| 1 | Twelfth Night | 1.0 | 3.6 | 3.6 |
| 2 | All's Well That Ends Well | 1.4 | 4.6 | 4.6 |
| 3 | Antony and Cleopatra | 3.0 | 8.4 | 8.4 |
| 4 | As You Like It | 1.4 | 4.4 | 4.4 |
| 5 | Comedy of Errors | 0.8 | 2.2 | 2.2 |
| 6 | Coriolanus | 2.0 | 5.6 | 5.6 |
| 8 | Hamlet | 1.4 | 4.0 | 4.0 |
| 10 | Henry IV, Part II | 0.833 | 3.333 | 3.333 |

**Calculation breakdown for "Twelfth Night":**
- Acts: 5 (Act 1, 2, 3, 4, 5)
- Total scenes (COUNT *): 18
- Distinct scene numbers (COUNT DISTINCT): 5 (scenes 1-5)
- Wrong: 5 / 5 = 1.0
- Correct: 18 / 5 = 3.6

**Impact:**
* Current implementation: **6/43 matches (14.0%)**
* Corrected implementation: **43/43 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The division formula is correct (`num_scenes / num_acts`), but the `num_scenes` component must count all chapter records (`COUNT(*)`) rather than distinct scene numbers (`COUNT(DISTINCT Scene)`), since scene numbers reset for each act.
