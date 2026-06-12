# Column Mismatch Summary

## Database: regional_sales
## Table: regional_sales__products
## Column: PERCENTAGE_OF_PRODUCTS_THAT_WERE_SHIPPED_FROM_BURBAN

### Description
The percentage of products that were shipped from Burban.

---

## Root Cause
**Two errors: (1) Wrong join column - using WarehouseCode instead of _StoreID, (2) Counting orders instead of Order_Quantity**

### Incorrect SQL Logic
```sql
store_locations AS (
    SELECT
        TO_VARCHAR(STOREID) AS store_id,
        CITY_NAME AS city_name
    FROM {{ source('airbyte_schema', 'STORE_LOCATIONS') }}
),

product_metrics AS (
    SELECT
        p.product_id,
        ROUND(
            100.0 * SUM(CASE WHEN sl.city_name = 'Burban' THEN 1 ELSE 0 END) /  -- Counts orders, not quantity
            NULLIF(COUNT(so.order_number), 0),
            2
        ) AS percentage_of_products_that_were_shipped_from_Burban,
        ...
    FROM products p
    LEFT JOIN sales_orders_with_metrics so ON p.product_id = so.product_id
    LEFT JOIN store_locations sl ON so.warehouse_code = sl.store_id  -- Wrong join!
    GROUP BY p.product_id, p.product_name
)
```

### Correct SQL Logic
```sql
store_locations AS (
    SELECT
        STOREID AS store_id,
        CITY_NAME AS city_name
    FROM {{ source('airbyte_schema', 'STORE_LOCATIONS') }}
),

product_metrics AS (
    SELECT
        p.product_id,
        ROUND(
            100.0 * SUM(CASE WHEN sl.city_name = 'Burbank' THEN so.order_quantity ELSE 0 END) /  -- Count quantity, "Burbank" not "Burban"
            NULLIF(SUM(so.order_quantity), 0),
            6
        ) AS percentage_of_products_that_were_shipped_from_Burban,
        ...
    FROM products p
    LEFT JOIN sales_orders_with_metrics so ON p.product_id = so.product_id
    LEFT JOIN store_locations sl ON so._store_id = sl.store_id  -- Correct: join on _StoreID
    GROUP BY p.product_id, p.product_name
)
```

---

## Why the Original Logic Is Wrong

### Error 1: Wrong join column
* **WarehouseCode** values: 'WARE-UHY1004', 'WARE-NMK1003', etc.
* **Store_Locations.storeid** values: 1, 2, 3, ... 367

These don't match. The correct join is `_StoreID` (from Sales_Orders) = `storeid` (from Store_Locations).

### Error 2: Counting orders vs quantities
* **What the column means**: Percentage of PRODUCT UNITS shipped from Burbank
* **What the SQL computes**: Percentage of ORDERS from Burbank

The description says "percentage of products" which refers to individual units (Order_Quantity), not the count of orders.

### Error 3: City name typo
The column name says "Burban" but the actual city in Store_Locations is "Burbank".

---

## Evidence

**Key comparison demonstrating the error:**

| Product ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| 4 | 0.00 | 0.911162 | 0.911162 |
| 5 | 0.00 | 0.123305 | 0.123305 |
| 7 | 0.00 | 0.272109 | 0.272109 |
| 8 | 0.00 | 0.796359 | 0.796359 |
| 9 | 0.00 | 1.424870 | 1.424870 |

**Example for Product 4:**
- Total Order_Quantity: 878 units
- Burbank Order_Quantity: 8 units
- Percentage: 8/878 × 100 = 0.911162%

**Impact:**
* Current implementation: **31/47 matches (66.0%)**
* Corrected implementation: **47/47 matches (100%)**

---

## Result
**Correction needed**

1. Join on `_StoreID` = `storeid` (not WarehouseCode)
2. Sum `Order_Quantity` instead of counting orders
3. Use city name 'Burbank' (not 'Burban')
