# Column Mismatch Summary

## Database: restaurant
## Table: cities
## Column: REVIEW_GREATER_THAN_AVERAGE_REVIEW_ALL_AMERICAN_RESTAURANTS

### Description (from data_model.yaml)
> Set to 3 if the average review of all restaurants in the city exceeds 90% of the average review of all American restaurants in the city, to 2 if it exceeds 70%, to 1 if it exceeds 50%, and to 0 otherwise.

---

## Status: CRITICAL MISMATCH - Wrong Comparison Logic

### Root Cause
The predicted values are all `0` while GT shows values of 0, 1, 2, or 3. The comparison logic may be incorrect:
1. GT may compare to GLOBAL average of ALL American restaurants (across all cities)
2. Predicted compares to city's OWN American restaurant average (per-city)

---

## SQL Logic Comparison

### Predicted SQL Logic (Incorrect - Per-City Comparison)
```sql
-- Compares city average to city's American restaurants
city_american_avg AS (
    SELECT city, AVG(review) as avg_review
    FROM generalinfo
    WHERE food_type = 'American'
    GROUP BY city
)
CASE
    WHEN city_avg >= 0.9 * city_american_avg THEN 3
    ...
END
```

### Correct SQL Logic (Global Comparison)
```sql
-- Calculate GLOBAL average of ALL American restaurants
global_american_avg AS (
    SELECT AVG(review) as avg_review
    FROM generalinfo
    WHERE food_type = 'American'
)

-- Compare each city's average to the GLOBAL American average
CASE
    WHEN city_avg > 0.9 * global_american_avg THEN 3
    WHEN city_avg > 0.7 * global_american_avg THEN 2
    WHEN city_avg > 0.5 * global_american_avg THEN 1
    ELSE 0
END
```

---

## Evidence

### Data Comparison

| City | GT Value | Predicted Value | Match |
|------|----------|-----------------|-------|
| alameda | 3.0 | 0 | **No** |
| berkeley | 3.0 | 0 | **No** |
| campbell | 3.0 | 0 | **No** |
| san francisco | 2.0 | 0 | **No** |
| inverness | 2.0 | 0 | **No** |

### Analysis
- GT has values: 0, 1, 2, or 3
- Predicted is always 0
- The comparison threshold logic exists but comparison base is wrong
- GT compares to global American restaurant average
- Predicted compares to per-city American average (which may not exist or be different)

---

## Result

**LOGIC ERROR** - The comparison should be against the GLOBAL average of all American restaurants, not a per-city average.

**Fix Required:**
```sql
-- Add global American average calculation
global_american_avg AS (
    SELECT AVG(review) as avg_review
    FROM generalinfo
    WHERE LOWER(food_type) = 'american'
),

-- Update comparison to use global average
CASE
    WHEN city_avg > 0.9 * (SELECT avg_review FROM global_american_avg) THEN 3
    WHEN city_avg > 0.7 * (SELECT avg_review FROM global_american_avg) THEN 2
    WHEN city_avg > 0.5 * (SELECT avg_review FROM global_american_avg) THEN 1
    ELSE 0
END AS review_greater_than_average_review_all_American_restaurants
```

**Key Insight:** "All American restaurants" in the description refers to the aggregate across the entire dataset, not per-city.
