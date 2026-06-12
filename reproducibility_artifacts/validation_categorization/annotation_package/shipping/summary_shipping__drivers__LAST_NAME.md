## Database: shipping
## Table: drivers
## Column: LAST_NAME

**Description:**
The last name of the driver.

---

## Root Cause
**Row ordering mismatch between ground truth and predicted results**

### Incorrect SQL Logic
```sql
-- Current SQL does not specify ORDER BY clause
SELECT
    ds.driver_id,
    ds.first_name,
    ds.last_name,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
-- No ORDER BY clause
```

### Correct SQL Logic
```sql
SELECT
    ds.driver_id,
    ds.first_name,
    ds.last_name,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
ORDER BY ds.driver_id ASC
```

---

## Why the Original Logic Is Wrong

* The LAST_NAME values are correctly retrieved from the source table
* The driver-to-last_name mapping is accurate (e.g., driver 20 = "Newell", driver 21 = "Simons")
* Row ordering difference causes position-based comparison to fail
* Ground truth row 1 has "Newell" (driver 20), predicted row 1 has "Nohr" (driver 27)

---

## Evidence

**Key comparison demonstrating the error:**

| Driver ID | Ground Truth LAST_NAME | Predicted LAST_NAME | Match? |
| --------- | ---------------------- | ------------------- | ------ |
| 20        | Newell                 | Newell              | Yes    |
| 21        | Simons                 | Simons              | Yes    |
| 22        | McHaney                | McHaney             | Yes    |
| 27        | Nohr                   | Nohr                | Yes    |

*Values match when compared by DRIVER_ID key, but fail when compared by row position*

**Impact:**
* Current implementation: **0/11 matches (0%)** (row-by-row comparison)
* Corrected implementation: **11/11 matches (100%)** (with ORDER BY driver_id)

---

## Result

**Row Ordering Issue - Add ORDER BY driver_id ASC**

**Key insight:**
The LAST_NAME values are correct for each driver. The comparison fails due to row ordering differences, not data correctness. Adding `ORDER BY driver_id ASC` resolves the issue.
