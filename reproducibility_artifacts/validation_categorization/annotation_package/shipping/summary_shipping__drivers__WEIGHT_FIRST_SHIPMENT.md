## Database: shipping
## Table: drivers
## Column: WEIGHT_FIRST_SHIPMENT

**Description:**
The weight the driver transported during his/her first shipment, with ties broken by the descending order of the weight.

---

## Root Cause
**Row ordering mismatch between ground truth and predicted results**

### Incorrect SQL Logic
```sql
-- Current SQL does not specify ORDER BY clause
SELECT
    ds.driver_id,
    ...
    fs.weight_first_shipment
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
-- No ORDER BY clause
```

### Correct SQL Logic
```sql
SELECT
    ds.driver_id,
    ...
    fs.weight_first_shipment
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
ORDER BY ds.driver_id ASC
```

---

## Why the Original Logic Is Wrong

* The WEIGHT_FIRST_SHIPMENT calculation logic is correct:
  - Uses ROW_NUMBER() with `PARTITION BY driver_id ORDER BY ship_date ASC, weight DESC`
  - Correctly identifies first shipment by earliest ship_date
  - Correctly breaks ties by selecting highest weight (DESC)
  - Joins with rn = 1 to get first shipment weight
* The computed values match ground truth for each driver
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Driver ID | Ground Truth | Predicted | Match? |
| --------- | ------------ | --------- | ------ |
| 20        | 5715.0       | 5715.0    | Yes    |
| 21        | 5697.0       | 5697.0    | Yes    |
| 22        | 17442.0      | 17442.0   | Yes    |
| 23        | 3528.0       | 3528.0    | Yes    |
| 27        | 8712.0       | 8712.0    | Yes    |

*All weight values match exactly when compared by DRIVER_ID key*

**Impact:**
* Current implementation: **0/11 matches (0%)** (row-by-row comparison)
* Corrected implementation: **11/11 matches (100%)** (with ORDER BY driver_id)

---

## Result

**Row Ordering Issue - Add ORDER BY driver_id ASC**

**Key insight:**
The WEIGHT_FIRST_SHIPMENT calculation is correct. The window function properly identifies the first shipment (earliest date, highest weight for ties) and retrieves its weight. The comparison fails solely due to row ordering.
