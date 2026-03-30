## Database: shipping
## Table: drivers
## Column: NUM_SHIPMENTS_2017

**Description:**
The number of shipments the driver delivered in 2017, replace NULL values with 0.

---

## Root Cause
**Row ordering mismatch between ground truth and predicted results**

### Incorrect SQL Logic
```sql
-- Current SQL does not specify ORDER BY clause
SELECT
    ds.driver_id,
    ...
    COALESCE(ds.num_shipments_2017, 0) AS num_shipments_2017,
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
    COALESCE(ds.num_shipments_2017, 0) AS num_shipments_2017,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
ORDER BY ds.driver_id ASC
```

---

## Why the Original Logic Is Wrong

* The NUM_SHIPMENTS_2017 calculation logic is correct:
  - `COUNT(CASE WHEN s.ship_year = 2017 THEN s.ship_id END)` correctly counts 2017 shipments
  - COALESCE properly handles NULL values with 0
* The computed values match ground truth for each driver
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Driver ID | Ground Truth | Predicted | Match? |
| --------- | ------------ | --------- | ------ |
| 20        | 48           | 48        | Yes    |
| 21        | 50           | 50        | Yes    |
| 22        | 49           | 49        | Yes    |
| 23        | 46           | 46        | Yes    |
| 27        | 50           | 50        | Yes    |

*All values match when compared by DRIVER_ID key*

**Impact:**
* Current implementation: **0/11 matches (0%)** (row-by-row comparison)
* Corrected implementation: **11/11 matches (100%)** (with ORDER BY driver_id)

---

## Result

**Row Ordering Issue - Add ORDER BY driver_id ASC**

**Key insight:**
The NUM_SHIPMENTS_2017 calculation is correct. The comparison fails due to row ordering differences. The SQL logic correctly filters shipments by year and counts them per driver.
