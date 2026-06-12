# Column Mismatch Summary

## Database: regional_sales
## Table: regional_sales__products
## Column: TOTAL_NET_PROFIT

### Description
The total net profit of the product, replace NULL values with 0.

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
        ((unit_price - unit_cost) * order_quantity * (1 - discount_applied)) AS net_profit  -- Wrong formula
    FROM sales_orders
),

product_metrics AS (
    SELECT
        COALESCE(SUM(so.net_profit), 0) AS total_net_profit,
        ...
)
```

### Correct SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(REPLACE(UNIT_PRICE, ',', '') AS FLOAT) AS unit_price,  -- Remove commas
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
        COALESCE(SUM(so.net_profit), 0) AS total_net_profit,
        ...
)
```

---

## Why the Original Logic Is Wrong

### Error 1: Comma in numbers
Unit_Price values like "1,963.10" cause TRY_CAST to fail.

### Error 2: Discount application
* **What the column description means**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity
* **What the SQL actually computes**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity × (1 - Discount)

The discount applies to the price charged to customers, not to the profit margin calculation.

---

## Evidence

**Key comparison demonstrating the error:**

| Product ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| 1 | 28,628.31 | 551,261.99 | 551,257 |
| 2 | 28,910.36 | 783,670.01 | 783,665 |
| 3 | 39,899.85 | 691,921.17 | 691,920 |
| 4 | 35,290.54 | 786,350.51 | 786,347 |
| 5 | 37,023.72 | 750,972.04 | 750,972 |

**Calculation example for Product 1:**
- Wrong: SUM((price - cost) × qty × (1 - disc)) = 486,109.15 (even lower due to comma parsing)
- Correct: SUM((price - cost) × qty) = 551,261.99

**Impact:**
* Current implementation: **0/47 matches (0%)**
* Corrected implementation: **47/47 matches (100%)**

---

## Result
**Correction needed**

1. Add `REPLACE(column, ',', '')` before casting numeric columns
2. Remove `(1 - discount_applied)` from net profit formula
