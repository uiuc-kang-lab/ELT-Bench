# Column Mismatch Summary

## Database: works_cycles
## Table: products
## Column: NUM_ORDERS

**Description:**
The number of orders the product has, replace null values with 0.

---

## Root Cause
**Wrong aggregation function: Using COUNT(*) instead of SUM(OrderQty)**

### Incorrect SQL Logic
```sql
orders AS (
    SELECT
        productid::INT AS product_id,
        COUNT(*) AS num_orders
    FROM {{ source('airbyte_schema', 'SalesOrderDetail') }}
    GROUP BY productid::INT
)
```

### Correct SQL Logic
```sql
orders AS (
    SELECT
        productid::INT AS product_id,
        SUM(orderqty) AS num_orders
    FROM {{ source('airbyte_schema', 'SalesOrderDetail') }}
    GROUP BY productid::INT
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The number of orders the product has" refers to the total quantity ordered for each product
  * This represents the sum of all units ordered across all order line items
  * The description says "number of orders" but semantically means "total quantity ordered"

* **What the SQL actually computes:**
  * COUNT(*) counts the number of order line items (rows in SalesOrderDetail)
  * Each row represents a line item in an order, but each line item can have OrderQty > 1
  * This underestimates the total quantity when customers order multiple units per line item

* **Schema insight from SalesOrderDetail:**
  * SalesOrderDetail contains: SalesOrderID, OrderQty, ProductID, etc.
  * OrderQty field holds the quantity ordered for each line item (can be 1 to 44)
  * Average OrderQty is approximately 2.27, meaning many orders have multiple units per line item

---

## Evidence

**Key comparison demonstrating the error:**

| ProductID | COUNT(*) (Wrong) | SUM(OrderQty) (Correct) | Ground Truth |
| --------- | ---------------- | ----------------------- | ------------ |
| 776       | 228              | 634                     | 634          |
| 777       | 242              | 678                     | 678          |
| 778       | 243              | 616                     | 616          |
| 771       | 241              | 642                     | 642          |
| 772       | 221              | 593                     | 593          |

**Formula verification for ProductID 776:**
- COUNT(*): 228 line items
- SUM(OrderQty): 634 total units ordered
- Ground Truth: 634
- Ratio GT/Predicted: 634/228 = 2.78 (average ~2.78 units per line item)

**Impact:**
* Current implementation: **254/504 matches (50.40%)**
* Corrected implementation: **504/504 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The term "number of orders" in the context of this data model actually refers to the total quantity of units ordered for each product. The SalesOrderDetail table stores order line items where each line can have an OrderQty greater than 1. To get the correct "number of orders," we must sum the OrderQty values rather than count the number of line item rows. Products without any orders correctly show 0 due to the COALESCE handling in the final select.
