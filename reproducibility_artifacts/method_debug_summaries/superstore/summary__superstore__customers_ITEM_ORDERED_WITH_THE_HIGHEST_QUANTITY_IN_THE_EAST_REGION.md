# Column Mismatch Summary

## Database: superstore
## Table: customers
## Column: ITEM_ORDERED_WITH_THE_HIGHEST_QUANTITY_IN_THE_EAST_REGION

**Description:**
The item ordered with the highest quantity in the East region by the customer, with ties broken by the descending order of the product name.

---

## Root Cause
**Product name lookup inconsistency: Product_ID maps to different Product_Names in source vs GT**

### Current SQL Logic
```sql
east_highest_qty AS (
    SELECT
        Customer_ID,
        Product_Name AS item_ordered_with_the_highest_quantity_in_the_East_region
    FROM (
        SELECT
            o.Customer_ID,
            p.Product_Name,
            o.Quantity,
            ROW_NUMBER() OVER (PARTITION BY o.Customer_ID ORDER BY o.Quantity DESC, p.Product_Name DESC) AS rn
        FROM all_orders o
        JOIN product p ON o.Product_ID = p.Product_ID
        WHERE o.Region = 'East'
    )
    WHERE rn = 1
)
```

---

## Why the Original Logic Is Mostly Correct

* **What the column description means:**
  * For orders in the East region, find the product with highest quantity
  * Break ties by descending product name

* **What the SQL computes:**
  * Filters to East region
  * Orders by Quantity DESC, Product_Name DESC
  * Picks the first result using ROW_NUMBER

* **The issue:**
  * Same Product_ID maps to different Product_Names in the `product` table vs GT
  * This is a data quality issue, not a logic error

---

## Evidence

**Sample mismatches:**

| Customer | GT Product Name | Pred Product Name |
| -------- | --------------- | ----------------- |
| BD-11635 | Ibico Recycled Linen-Style Covers | Belkin F5C206VTEL 6 Outlet Surge |
| BE-11455 | Howard Miller 13-3/4"... Round Wall Clock | DAX Solid Wood Frames |
| BF-11215 | Howard Miller 13" Diameter... | Eldon 200 Class Desk Accessories |

The Product_IDs are the same, but the Product_Names differ between GT source and the `product` table used by SQL.

**Impact:**
* Current implementation: **767/793 matches (96.72%)**
* 26 customers have different product names due to data inconsistency

---

## Result

**Near-perfect match - data quality issue in product table**

The SQL logic is correct. The mismatches are caused by the `product` source table having different Product_Name values for some Product_IDs compared to what GT expects. This is a data mapping issue, not a SQL logic error.
