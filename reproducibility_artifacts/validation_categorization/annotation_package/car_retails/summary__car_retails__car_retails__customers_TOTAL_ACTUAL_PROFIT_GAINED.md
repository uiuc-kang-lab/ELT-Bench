# Column Mismatch Summary

## Database: car_retails
## Table: car_retails__customers
## Column: TOTAL_ACTUAL_PROFIT_GAINED

### Description
Total actual profit gained from the customer, replace NULL values with 0.

---

## Root Cause
**Two errors: (1) Multiplies by quantity when it shouldn't, (2) Filters to 'Shipped' orders when all orders should be included**

### Incorrect SQL Logic
```sql
total_profit AS (
    SELECT
        o.customerNumber,
        SUM(od.quantityOrdered * (od.priceEach - p.buyPrice)) AS total_actual_profit_gained
    FROM orders o
    JOIN orderdetails od ON o.orderNumber = od.orderNumber
    JOIN products p ON od.productCode = p.productCode
    WHERE o.status = 'Shipped'
    GROUP BY o.customerNumber
)
```

### Correct SQL Logic
```sql
total_profit AS (
    SELECT
        o.customerNumber,
        SUM(od.priceEach - p.buyPrice) AS total_actual_profit_gained
    FROM orders o
    JOIN orderdetails od ON o.orderNumber = od.orderNumber
    JOIN products p ON od.productCode = p.productCode
    -- No filter on status - include all orders
    GROUP BY o.customerNumber
)
```

---

## Why the Original Logic Is Wrong

1. **Quantity Multiplication Error:**
   * The SQL calculates: `SUM(quantityOrdered * (priceEach - buyPrice))`
   * This gives total profit considering all units ordered
   * The correct formula is: `SUM(priceEach - buyPrice)` - per order line, not per unit
   * The term "actual profit gained" refers to the profit margin per order line, not total profit per unit

2. **Order Status Filter Error:**
   * The SQL filters `WHERE status = 'Shipped'`
   * The ground truth includes all orders regardless of status
   * An order's profit should be counted even if it hasn't shipped yet

---

## Evidence

**Key comparison demonstrating the error:**

| Customer | Wrong Logic (qty * margin, shipped) | Correct Logic (margin only, all) | Ground Truth |
| -------- | ----------------------------------- | -------------------------------- | ------------ |
| 103      | 10,063.80                           | 273.60                           | 273.60       |
| 112      | 31,312.72                           | 971.65                           | 971.65       |
| 114      | 70,311.07                           | 2,009.98                         | 2,009.98     |
| 119      | 45,587.79                           | 1,728.40                         | 1,728.40     |
| 121      | 41,391.52                           | 1,258.84                         | 1,258.84     |

**Example for customer 119:**
- Has 4 orders (3 Shipped, 1 In Process)
- Wrong calculation includes only shipped orders and multiplies by quantity: ~45,588
- Correct calculation includes all orders without quantity multiplier: 1,728.40

**Impact:**
* Current implementation: **24/122 matches (19.7%)**
* Corrected implementation: **122/122 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
"Total actual profit gained" means the sum of profit margins per order line (priceEach - buyPrice) across all orders, not the total profit per unit sold. The profit is calculated per order line regardless of quantity ordered.
