# Column Mismatch Summary

## Database: sales
## Table: sales__products
## Column: PER_SOLD

### Description
The percentage of the product sold in the total number of products sold.

---

## Root Cause
**Excessive rounding - SQL uses ROUND(..., 2) but ground truth expects full precision**

### Incorrect SQL Logic
```sql
SELECT
    pa.productid as ProductID,
    pa.name as Name,
    pa.price as Price,
    CASE
        WHEN tp.total_qty > 0 THEN ROUND((pa.total_quantity * 100.0 / tp.total_qty), 2)
        ELSE 0
    END as per_sold,
    ...
FROM product_aggregates pa
CROSS JOIN total_products_sold tp
```

### Correct SQL Logic
```sql
SELECT
    pa.productid as ProductID,
    pa.name as Name,
    pa.price as Price,
    CASE
        WHEN tp.total_qty > 0 THEN (pa.total_quantity * 100.0 / tp.total_qty)
        ELSE 0
    END as per_sold,
    ...
FROM product_aggregates pa
CROSS JOIN total_products_sold tp
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The percentage calculation should preserve full precision
* **What the SQL actually computes**: Rounds the result to 2 decimal places using ROUND(..., 2)

The formula `(total_quantity * 100.0 / total_qty)` is correct, but the ROUND function loses precision. Ground truth values have full floating-point precision (e.g., 0.05036648782962833), while predicted values are rounded to 2 decimals (e.g., 0.05).

---

## Evidence

**Key comparison demonstrating the error:**

| ProductID | Name | Correct Logic | Rounded (2 dec) | Ground Truth |
| --------- | ---- | ------------- | --------------- | ------------ |
| 1 | Adjustable Race | 0.050366 | 0.05 | 0.050366 |
| 2 | Bearing Ball | 0.045205 | 0.05 | 0.045205 |
| 9 | Chainring Bolts | 0.526384 | 0.53 | 0.526384 |
| 10 | Chainring Nut | 0.447680 | 0.45 | 0.447680 |
| 39 | Thin-Jam Hex Nut 10 | 0.159338 | 0.16 | 0.159338 |

**Analysis:**
- Matches with no rounding: 504/504 (100%)
- Matches with ROUND(..., 2): 92/504 (18.3%)

**Impact:**
* Current implementation: **0/504 exact matches (0%)**
* Corrected implementation: **504/504 matches (100%)**

---

## Result
**Correction needed**

Remove `ROUND(..., 2)` from the per_sold calculation to preserve full floating-point precision:
```sql
-- Change from:
ROUND((pa.total_quantity * 100.0 / tp.total_qty), 2)
-- To:
(pa.total_quantity * 100.0 / tp.total_qty)
```
