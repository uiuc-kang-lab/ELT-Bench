# Column Mismatch Summary

## Database: sales
## Table: sales__customers
## Column: PRODUCT_WITH_THE_HIGHEST_QUANTITY

### Description
The product with the highest quantity the customer has bought, with ties broken by the ascending order of the product name

---

## Root Cause
**Aggregation level error - SQL finds max quantity from individual sales records instead of total quantity per product**

### Incorrect SQL Logic
```sql
product_with_highest_qty AS (
    SELECT
        CustomerID,
        ProductName,
        Quantity,
        ROW_NUMBER() OVER (PARTITION BY CustomerID ORDER BY Quantity DESC, ProductName ASC) as rn
    FROM customer_sales
    WHERE Quantity IS NOT NULL
)

SELECT
    ...
    COALESCE(ph.ProductName, '') as product_with_the_highest_quantity,
FROM customer_aggregates ca
LEFT JOIN product_with_highest_qty ph ON ca.CustomerID = ph.CustomerID AND ph.rn = 1
```

### Correct SQL Logic
```sql
customer_product_totals AS (
    SELECT
        CustomerID,
        ProductName,
        SUM(Quantity) as total_quantity
    FROM customer_sales
    WHERE Quantity IS NOT NULL
    GROUP BY CustomerID, ProductName
),

product_with_highest_qty AS (
    SELECT
        CustomerID,
        ProductName,
        total_quantity,
        ROW_NUMBER() OVER (PARTITION BY CustomerID ORDER BY total_quantity DESC, ProductName ASC) as rn
    FROM customer_product_totals
)

SELECT
    ...
    COALESCE(ph.ProductName, '') as product_with_the_highest_quantity,
FROM customer_aggregates ca
LEFT JOIN product_with_highest_qty ph ON ca.CustomerID = ph.CustomerID AND ph.rn = 1
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the product with the highest TOTAL quantity the customer has bought across all their orders
* **What the SQL actually computes**: Finds the product from the individual sale record with the highest single quantity

The difference is:
- **Current SQL**: Picks the product from the single sale with max quantity (e.g., one order of 988 units)
- **Ground Truth**: Sums all quantities per product, then picks the product with highest total (e.g., 500 orders totaling 160,797 units)

---

## Evidence

**Key comparison demonstrating the error:**

**Customer 8:**
| Method | Product | Quantity |
| ------ | ------- | -------- |
| Wrong (max single sale) | Touring-3000 Blue, 44 | 988 |
| Correct (sum by product) | ML Road Frame - Red, 44 | 160,797 |
| Ground Truth | ML Road Frame - Red, 44 | - |

**Customer 47:**
| Method | Product | Quantity |
| ------ | ------- | -------- |
| Wrong (max single sale) | Road-650 Red, 58 | 264 |
| Correct (sum by product) | HL Mountain Frame - Silver, 46 | 67,925 |
| Ground Truth | HL Mountain Frame - Silver, 46 | - |

**Customer 80:**
| Method | Product | Quantity |
| ------ | ------- | -------- |
| Wrong (max single sale) | ML Mountain Frame - Black, 38 | 824 |
| Correct (sum by product) | HL Mountain Rear Wheel | 7,965,566 |
| Ground Truth | HL Mountain Rear Wheel | - |

**Impact:**
* Current implementation: **19,559/19,759 matches (99.0%)**
* Corrected implementation: **19,759/19,759 matches (100%)**

---

## Result
**Correction needed**

1. Add an intermediate aggregation step to sum quantities by (CustomerID, ProductID)
2. Apply ROW_NUMBER on the aggregated totals instead of individual sale records
3. Keep the tiebreaker logic (ProductName ASC) unchanged
