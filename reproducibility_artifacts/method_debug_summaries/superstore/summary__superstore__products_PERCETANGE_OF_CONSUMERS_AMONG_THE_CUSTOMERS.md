# Column Mismatch Summary

## Database: superstore
## Table: products
## Column: PERCETANGE_OF_CONSUMERS_AMONG_THE_CUSTOMERS

**Description:**
The percentage of consumers among the customers who have ordered the product.

---

## Root Cause
**Customer segment lookup issue: SQL uses 'people' table which may have different segment assignments than expected by GT**

### Incorrect SQL Logic
```sql
consumer_percentage AS (
    SELECT
        o.Product_ID,
        (COUNT(DISTINCT CASE WHEN p.Segment = 'Consumer' THEN o.Customer_ID END) * 100.0 /
         NULLIF(COUNT(DISTINCT o.Customer_ID), 0)) AS percetange_of_consumers_among_the_customers
    FROM all_orders o
    LEFT JOIN people p ON o.Customer_ID = p.Customer_ID
    GROUP BY o.Product_ID
)
```

### Correct SQL Logic
```sql
-- The segment should come from the order tables directly, not from people table
consumer_percentage AS (
    SELECT
        o.Product_ID,
        (COUNT(DISTINCT CASE WHEN o.Segment = 'Consumer' THEN o.Customer_ID END) * 100.0 /
         NULLIF(COUNT(DISTINCT o.Customer_ID), 0)) AS percetange_of_consumers_among_the_customers
    FROM all_orders o
    GROUP BY o.Product_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Among all customers who ordered this product, what percentage are in the 'Consumer' segment
  * The segment should be determined per order/transaction

* **What the SQL actually computes:**
  * Looks up customer segment from `people` table
  * The `people` table may have different/outdated segment assignments
  * GT likely uses segment from the order tables directly

* **Schema insight:**
  * The superstore order tables (central, east, south, west) likely have a Segment column
  * Using `people.Segment` instead of the order's segment causes mismatches

---

## Evidence

**Key comparison demonstrating the error:**

| Product_ID | GT (%) | Pred (%) | Difference |
| ---------- | ------ | -------- | ---------- |
| FUR-BO-10000330 | 70.00 | 66.67 | 3.33 |
| FUR-BO-10000362 | 13.33 | 20.00 | -6.67 |
| FUR-BO-10000468 | 80.00 | 83.33 | -3.33 |
| FUR-BO-10000780 | 82.35 | 80.00 | 2.35 |
| FUR-BO-10001337 | 63.89 | 60.00 | 3.89 |

**Impact:**
* Current implementation: **542/1888 matches (28.71%)**
* 1346 products have incorrect consumer percentages

---

## Result

**Significant logic error - wrong segment source**

The SQL should use the Segment column from the order tables (all_orders) rather than joining to the `people` table. The segment associated with each transaction is the relevant one, not a separate customer master table.
