# Column Mismatch Summary: HAS_WEIGHT_GREATER_THAN_79_PER_AVG_WEIGHT

## Database: superhero
## Table: superheroes
## Column: HAS_WEIGHT_GREATER_THAN_79_PER_AVG_WEIGHT

### Description
Set to 1 if the superhero has a weight greater than the 79% average weight of all superheroes, otherwise, set to 0.

---

## Root Cause: Misinterpretation of "79% average weight" as 79th Percentile

The SQL incorrectly uses `PERCENTILE_CONT(0.79)` to calculate the 79th percentile of weights, when the column description asks for "79% of the average weight" (i.e., 0.79 * AVG(weight)).

### Incorrect SQL (Predicted)
```sql
percentile_79_weight AS (
    SELECT PERCENTILE_CONT(0.79) WITHIN GROUP (ORDER BY WEIGHT_KG) AS weight_79_percentile
    FROM superhero_base
    WHERE WEIGHT_KG IS NOT NULL
),

-- Later in main query:
CASE
    WHEN sb.WEIGHT_KG > (SELECT weight_79_percentile FROM percentile_79_weight) THEN 1
    ELSE 0
END AS has_weight_greater_than_79_per_avg_weight
```

### Correct SQL (Required)
```sql
avg_weight AS (
    SELECT AVG(WEIGHT_KG) AS avg_weight_value
    FROM superhero_base
    WHERE WEIGHT_KG IS NOT NULL AND WEIGHT_KG > 0
),

-- Later in main query:
CASE
    WHEN sb.WEIGHT_KG > (0.79 * (SELECT avg_weight_value FROM avg_weight)) THEN 1
    ELSE 0
END AS has_weight_greater_than_79_per_avg_weight
```

---

## Why the Original Logic Is Wrong

1. **Mathematical Misunderstanding:**
   - "79% average weight" = 0.79 * AVG(weight_kg) = 0.79 * 192,878.47 = 152,373.99 kg
   - "79th percentile" = PERCENTILE_CONT(0.79) = 126.00 kg
   - These are completely different values

2. **Impact on Results:**
   - Predicted counts 142 heroes with weight > 126 kg (79th percentile)
   - Ground truth counts only 2 heroes with weight > 152,373.99 kg (79% of average)
   - The 140 row difference (142 vs 2) represents heroes between 126 kg and 152,373.99 kg

3. **Note on Average Weight:**
   - The average weight (192,878.47 kg) is extremely high due to outliers (cosmic/massive superheroes)
   - Only 2 heroes exceed 79% of this average, as expected in the ground truth

---

## Evidence

### Threshold Comparison

| Calculation Method | Threshold Value | Count Flag=1 |
|-------------------|-----------------|--------------|
| 79th Percentile (Predicted) | 126.00 kg | 142 |
| 79% of Average (Ground Truth) | 152,373.99 kg | 2 |

### Sample Data Showing Discrepancy

| Hero ID | Superhero Name | Weight (kg) | Predicted | Ground Truth |
|---------|---------------|-------------|-----------|--------------|
| 2 | A-Bomb | ~135 | 1 | 0 |
| 5 | Abomination | ~180 | 1 | 0 |
| 7 | Absorbing Man | ~122 | 1 | 0 |
| 13 | Air-Walker | ~108 | 1 | 0 |

### Statistical Summary

```
Superheroes with valid weight: 514
Average weight: 192,878.47 kg
79% of average: 152,373.99 kg
79th percentile: 126.00 kg

Distribution of flag values:
- Predicted: {0: 608, 1: 142}
- Ground Truth: {0: 748, 1: 2}
```

---

## Impact

| Metric | Value |
|--------|-------|
| Total Rows | 750 |
| Mismatched Rows | 140 |
| Match Rate | 81.3% |
| Root Cause | PERCENTILE_CONT vs arithmetic calculation |

---

## Result

**Status:** MISMATCH

The column fails validation due to:
1. Using `PERCENTILE_CONT(0.79)` instead of `0.79 * AVG(WEIGHT_KG)`
2. Resulting in 140 extra rows incorrectly flagged as 1

**Fix Required:**
1. Replace `PERCENTILE_CONT(0.79) WITHIN GROUP (ORDER BY WEIGHT_KG)` with `0.79 * AVG(WEIGHT_KG)`
2. Ensure NULL and zero weights are excluded from the average calculation
