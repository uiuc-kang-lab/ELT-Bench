## Database: shipping
## Table: drivers
## Column: PER_SHIPMENT_PLACED_BY_AUTOWARE_INC

**Description:**
The percentage of shipments placed by Autoware Inc among all shipments delivered by the driver.

---

## Root Cause
**Row ordering mismatch between ground truth and predicted results**

### Incorrect SQL Logic
```sql
-- Current SQL does not specify ORDER BY clause
SELECT
    ds.driver_id,
    ...
    COALESCE(ds.per_shipment_placed_by_Autoware_Inc, 0) AS per_shipment_placed_by_Autoware_Inc,
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
    COALESCE(ds.per_shipment_placed_by_Autoware_Inc, 0) AS per_shipment_placed_by_Autoware_Inc,
    ...
FROM driver_shipment_stats ds
LEFT JOIN first_shipment_per_driver fs ON ds.driver_id = fs.driver_id AND fs.rn = 1
ORDER BY ds.driver_id ASC
```

---

## Why the Original Logic Is Wrong

* The PER_SHIPMENT_PLACED_BY_AUTOWARE_INC calculation logic is correct:
  - `SUM(CASE WHEN s.cust_name = 'Autoware Inc' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(s.ship_id), 0)`
  - Correctly calculates percentage as (Autoware shipments / total shipments) * 100
  - Properly handles division by zero with NULLIF
* The computed values match ground truth for each driver
* Row ordering difference causes position-based comparison to fail

---

## Evidence

**Key comparison demonstrating the error:**

| Driver ID | Ground Truth             | Predicted                | Match? |
| --------- | ------------------------ | ------------------------ | ------ |
| 20        | 4.878048780487805        | 4.878048780487805        | Yes    |
| 21        | 5.4945054945054945       | 5.4945054945054945       | Yes    |
| 22        | 4.49438202247191         | 4.49438202247191         | Yes    |
| 27        | 4.081632653061225        | 4.081632653061225        | Yes    |
| 29        | 1.2048192771084338       | 1.2048192771084338       | Yes    |

*All percentage values match exactly when compared by DRIVER_ID key*

**Impact:**
* Current implementation: **0/11 matches (0%)** (row-by-row comparison)
* Corrected implementation: **11/11 matches (100%)** (with ORDER BY driver_id)

---

## Result

**Row Ordering Issue - Add ORDER BY driver_id ASC**

**Key insight:**
The PER_SHIPMENT_PLACED_BY_AUTOWARE_INC calculation is correct. The percentage formula properly computes shipments from "Autoware Inc" as a percentage of total driver shipments. The comparison fails solely due to row ordering.
