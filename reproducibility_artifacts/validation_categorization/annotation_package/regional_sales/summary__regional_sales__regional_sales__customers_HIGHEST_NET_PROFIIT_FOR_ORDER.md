# Column Mismatch Summary

## Database: regional_sales
## Table: regional_sales__customers
## Column: HIGHEST_NET_PROFIIT_FOR_ORDER

### Description
The highest net profit for an order the customer has made.

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
)
```

### Correct SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(REPLACE(UNIT_PRICE, ',', '') AS FLOAT) AS unit_price,  -- Remove commas first
        TRY_CAST(REPLACE(UNIT_COST, ',', '') AS FLOAT) AS unit_cost,
        ...
    FROM {{ source('airbyte_schema', 'SALES_ORDERS') }}
),

sales_orders_with_metrics AS (
    SELECT
        *,
        ((unit_price - unit_cost) * order_quantity) AS net_profit  -- No discount multiplier
    FROM sales_orders
)
```

---

## Why the Original Logic Is Wrong

### Error 1: Comma in numbers
The source data has Unit_Price formatted with commas (e.g., "1,963.10"). TRY_CAST fails or returns NULL for these values.

### Error 2: Discount application
* **What the column description means**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity
* **What the SQL actually computes**: Net profit = (Unit_Price - Unit_Cost) × Order_Quantity × (1 - Discount)

The discount is applied to revenue for the customer, not to the profit margin. Net profit is calculated before applying customer discounts.

---

## Evidence

**Key comparison demonstrating the error:**

| Customer ID | Wrong Logic | Correct Logic | Ground Truth |
| ----------- | ----------- | ------------- | ------------ |
| 1 | 3,665.25 | 21,178.15 | 21,175 |
| 2 | 3,203.86 | 30,915.46 | 30,912 |
| 3 | 2,950.01 | 24,466.32 | 24,465 |
| 4 | 2,866.71 | 26,849.25 | 26,848 |
| 5 | 2,765.76 | 22,890.74 | 22,890 |

**Calculation example for Customer 1:**
- Highest profit order: (Unit_Price - Unit_Cost) × Order_Quantity
- = ($5,708.40 - $1,878.25) × 7 = $3,830.15 × 7 = $26,811.05 (one order)
- But wrong formula: $26,811.05 × (1 - 0.05) = $25,470.50

**Impact:**
* Current implementation: **0/50 matches (0%)**
* Corrected implementation: **50/50 matches (100%)**

---

## Result
**Correction needed**

1. Add `REPLACE(column, ',', '')` before casting numeric columns
2. Remove `(1 - discount_applied)` from net profit formula
