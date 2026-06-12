## Database: shipping
## Table: drivers
## Column: NUM_SHIPMENT_TO_LEAST_POPULATED_CITY

**Description:**
The number of shipments to the least populated city delivered by the driver, replace NULL values with 0.

---

## Root Cause
**Row ordering mismatch between ground truth and predicted results**

### Incorrect SQL Logic
```sql
-- Current SQL does not specify ORDER BY clause
SELECT
    ds.driver_id,
    ...
    COALESCE(ds.num_shipment_to_least_populated_city, 0) AS num_shipment_to_least_populated_city,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
-- No ORDER BY clause
```

### Correct SQL Logic
```sql
SELECT
    ds.driver_id,
    ...
    COALESCE(ds.num_shipment_to_least_populated_city, 0) AS num_shipment_to_least_populated_city,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
ORDER BY ds.driver_id ASC
```

---

## Why the Original Logic Is Wrong

* The NUM_SHIPMENT_TO_LEAST_POPULATED_CITY calculation logic is correct:
  - Identifies least populated city via ROW_NUMBER() ordered by population ASC
  - Counts shipments to that specific city for each driver
  - COALESCE properly handles NULL values with 0
* The computed values match ground truth for each driver
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Driver ID | Ground Truth | Predicted | Match? |
| --------- | ------------ | --------- | ------ |
| 20        | 0            | 0         | Yes    |
| 21        | 1            | 1         | Yes    |
| 22        | 0            | 0         | Yes    |
| 23        | 0            | 0         | Yes    |
| 27        | 0            | 0         | Yes    |

*Only driver 21 (Andrea Simons) has a shipment to the least populated city*

**Impact:**
* Current implementation: **0/11 matches (0%)** (row-by-row comparison)
* Corrected implementation: **11/11 matches (100%)** (with ORDER BY driver_id)

---

## Result

**Row Ordering Issue - Add ORDER BY driver_id ASC**

**Key insight:**
The NUM_SHIPMENT_TO_LEAST_POPULATED_CITY calculation is correct. The subquery correctly identifies the least populated city and counts shipments accordingly. The comparison fails solely due to row ordering.
