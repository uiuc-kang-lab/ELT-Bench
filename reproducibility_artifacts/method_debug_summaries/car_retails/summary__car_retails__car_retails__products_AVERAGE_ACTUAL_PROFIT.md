# Column Mismatch Summary

## Database: car_retails
## Table: car_retails__products
## Column: AVERAGE_ACTUAL_PROFIT

### Description
Average actual profit gained from the product.

---

## Root Cause
**Aggregation method: SQL uses simple average per order line, but GT uses quantity-weighted average**

### Incorrect SQL Logic
```sql
avg_profit AS (
    SELECT
        od.productCode,
        AVG(od.priceEach - p.buyPrice) AS average_actual_profit
    FROM orderdetails od
    JOIN products p ON od.productCode = p.productCode
    GROUP BY od.productCode
)
```

### Correct SQL Logic
```sql
avg_profit AS (
    SELECT
        od.productCode,
        SUM((od.priceEach - p.buyPrice) * od.quantityOrdered) / SUM(od.quantityOrdered) AS average_actual_profit
    FROM orderdetails od
    JOIN products p ON od.productCode = p.productCode
    GROUP BY od.productCode
)
```

---

## Why the Original Logic Is Wrong

* The SQL calculates: `AVG(priceEach - buyPrice)` - simple average across order lines
* This treats each order line equally regardless of quantity
* The correct formula is a quantity-weighted average: `SUM(profit * qty) / SUM(qty)`
* This gives the true average profit per unit sold

**Example:**
- Order line 1: profit = $10, quantity = 100 units
- Order line 2: profit = $20, quantity = 10 units
- Simple average: ($10 + $20) / 2 = $15
- Weighted average: ($10*100 + $20*10) / (100+10) = $1,200 / 110 = $10.91

The weighted average reflects the actual profit per unit considering volume.

---

## Evidence

**Key comparison demonstrating the error:**

| Product Code | Simple AVG | Weighted AVG | Ground Truth |
| ------------ | ---------- | ------------ | ------------ |
| S10_1678     | 36.36      | 36.49        | 36.49        |
| S10_1949     | 98.73      | 99.15        | 99.15        |
| S10_2016     | 41.03      | 41.12        | 41.12        |
| S10_4698     | 81.27      | 82.27        | 82.27        |
| S10_4757     | 38.57      | 38.52        | 38.52        |
| S10_4962     | 28.39      | 28.69        | 28.69        |

The differences are small but consistent - weighted average always matches GT.

**Impact:**
* Current implementation: **4/110 matches (3.6%)**
* Corrected implementation: **109/110 matches (99.1%)**

Note: 1 product has NULL value in both GT and calculated result (no orders).

---

## Result
**Perfect match with corrected logic**

**Key insight:**
"Average actual profit" means the weighted average profit per unit sold. The weighting by quantity ensures that order lines with more units have proportionally more influence on the average, reflecting the true economics of sales.
