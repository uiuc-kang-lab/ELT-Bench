# Column Mismatch Summary

## Database: regional_sales
## Table: regional_sales__products
## Column: HIGHEST_NET_PROFIT_IN_2019

### Description
The highest net profit of the product in 2019.

---

## Root Cause
**Two errors: (1) Comma in numeric strings not handled, (2) Discount incorrectly applied to profit calculation**

### Incorrect SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(UNIT_PRICE AS FLOAT) AS unit_price,  -- Fails on "1,963.10"
        TRY_CAST(UNIT_COST AS FLOAT) AS unit_cost,
        ...
    FROM {{ source('airbyte_schema', 'SALES_ORDERS') }}
),

sales_orders_with_metrics AS (
    SELECT
        *,
        ((unit_price - unit_cost) * order_quantity * (1 - discount_applied)) AS net_profit
    FROM sales_orders
),

product_metrics AS (
    SELECT
        MAX(CASE WHEN YEAR(so.order_date) = 2019 THEN so.net_profit ELSE NULL END) AS highest_net_profit_in_2019,
        ...
)
```

### Correct SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(REPLACE(UNIT_PRICE, ',', '') AS FLOAT) AS unit_price,
        TRY_CAST(REPLACE(UNIT_COST, ',', '') AS FLOAT) AS unit_cost,
        ...
    FROM {{ source('airbyte_schema', 'SALES_ORDERS') }}
),

sales_orders_with_metrics AS (
    SELECT
        *,
        ((unit_price - unit_cost) * order_quantity) AS net_profit  -- No discount multiplier
    FROM sales_orders
),

product_metrics AS (
    SELECT
        MAX(CASE WHEN YEAR(so.order_date) = 2019 THEN so.net_profit ELSE NULL END) AS highest_net_profit_in_2019,
        ...
)
```

---

## Why the Original Logic Is Wrong

### Error 1: Comma in numbers
Unit_Price values like "1,963.10" cause TRY_CAST to fail or return incorrect values.

### Error 2: Discount application
* **What the column description means**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity
* **What the SQL actually computes**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity × (1 - Discount)

---

## Evidence

**Key comparison demonstrating the error:**

| Product ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| 1 | 3,193.73 | 20,846.14 | 20,846 |
| 2 | 2,444.26 | 30,915.46 | 30,912 |
| 3 | 3,435.89 | 18,128.40 | 18,128 |
| 4 | 2,726.77 | 18,328.17 | 18,328 |
| 5 | 3,108.49 | 25,151.60 | 25,151 |

**Example for Product 1:**
- Wrong calculation: MAX((price - cost) × qty × (1 - disc)) for 2019 orders ≈ 19,282.68
- Correct calculation: MAX((price - cost) × qty) for 2019 orders = 20,846.14

**Impact:**
* Current implementation: **0/47 matches (0%)**
* Corrected implementation: **47/47 matches (100%)**

---

## Result
**Correction needed**

1. Add `REPLACE(column, ',', '')` before casting numeric columns
2. Remove `(1 - discount_applied)` from net profit formula
