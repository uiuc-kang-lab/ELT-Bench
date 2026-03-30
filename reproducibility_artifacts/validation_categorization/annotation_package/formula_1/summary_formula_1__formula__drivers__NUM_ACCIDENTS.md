# Column Mismatch Summary

## Database: formula_1
## Table: formula__drivers
## Column: NUM_ACCIDENTS

### Description
The number of accidents the driver has been involved in, replace NULL values with 0.

---

## Root Cause
**OVER-INCLUSIVE FILTER - LIKE pattern matches too many status values**

### Incorrect SQL Logic
```sql
SELECT r.driverId, COUNT(*) AS num_accidents
FROM results r
JOIN status s ON r.statusId = s.statusId
WHERE LOWER(s.status) LIKE '%accident%'
   OR LOWER(s.status) LIKE '%collision%'
   OR LOWER(s.status) LIKE '%crash%'
GROUP BY r.driverId
```

### Correct SQL Logic
```sql
SELECT r.driverId, COUNT(*) AS num_accidents
FROM results r
JOIN status s ON r.statusId = s.statusId
WHERE s.status = 'Accident'  -- Exact match only
GROUP BY r.driverId
```

---

## Why the Original Logic Is Wrong

* Predicted uses broad pattern matching (LIKE '%accident%', '%collision%', '%crash%')
* Ground Truth likely uses exact match on specific status value(s)
* The LIKE patterns match too many status values, overcounting accidents
* For example, "Collision damage" may not be classified as an "accident" in GT

---

## Evidence

**Key comparison demonstrating the error:**

| Driver | GT Value | Predicted Value | Ratio |
|--------|----------|-----------------|-------|
| Lewis Hamilton | 1 | 11 | 11x |
| Nick Heidfeld | 4 | 15 | 3.75x |
| Kimi Raikkonen | 8 | 19 | 2.4x |

Predicted values are consistently higher due to over-inclusive filtering.

---

## Result

**Status**: SEMANTIC MISINTERPRETATION - Over-inclusive filter

The accident count is overcounted because the LIKE pattern matches more status values than the ground truth's exact match filter.
