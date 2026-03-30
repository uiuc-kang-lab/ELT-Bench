# Column Mismatch Summary

## Database: regional_sales
## Table: regional_sales__customers
## Column: AVG_PRICE_OF_ORDER_AFTER_DISCOUNT

### Description
The average price of an order after discount the customer has made.

---

## Root Cause
**Comma in numeric strings not handled - TRY_CAST fails on values like "1,963.10"**

### Incorrect SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(UNIT_PRICE AS FLOAT) AS unit_price,  -- Fails on "1,963.10"
        ...
    FROM {{ source('airbyte_schema', 'SALES_ORDERS') }}
),

sales_orders_with_metrics AS (
    SELECT
        *,
        (unit_price * order_quantity * (1 - discount_applied)) AS order_value,
        ...
    FROM sales_orders
)

-- In customer_metrics:
AVG(so.order_value) AS avg_price_of_order_after_discount
```

### Correct SQL Logic
```sql
sales_orders AS (
    SELECT
        TRY_CAST(REPLACE(UNIT_PRICE, ',', '') AS FLOAT) AS unit_price,  -- Remove commas first
        ...
    FROM {{ source('airbyte_schema', 'SALES_ORDERS') }}
),

sales_orders_with_metrics AS (
    SELECT
        *,
        (unit_price * order_quantity * (1 - discount_applied)) AS order_value,
        ...
    FROM sales_orders
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Average of (Unit_Price × Order_Quantity × (1 - Discount))
* **What the SQL actually computes**: The formula is correct, but Unit_Price values with commas (e.g., "1,963.10") cause TRY_CAST to fail

The source data has Unit_Price formatted with thousands separators (commas). For example:
- "1,963.10" should be 1963.10
- "3,939.60" should be 3939.60

Without removing commas, TRY_CAST returns NULL or incorrect values.

---

## Evidence

**Key comparison demonstrating the error:**

| Customer ID | Wrong Logic | Correct Logic | Ground Truth |
| ----------- | ----------- | ------------- | ------------ |
| 1 | 2,027.95 | 7,730.40 | 7,730.58 |
| 2 | 2,293.86 | 8,735.75 | 8,735.91 |
| 3 | 1,805.44 | 8,996.02 | 8,996.11 |
| 4 | 2,563.04 | 9,398.32 | 9,398.32 |
| 5 | 2,134.76 | 8,969.73 | 8,969.72 |

**Sample Unit_Price values in source:**
- "1,963.10", "3,939.60", "1,775.50", "2,324.90"

**Impact:**
* Current implementation: **0/50 matches (0%)**
* Corrected implementation: **50/50 matches (100%)**

---

## Result
**Correction needed**

Add `REPLACE(UNIT_PRICE, ',', '')` before casting to properly parse numeric values with thousands separators.
