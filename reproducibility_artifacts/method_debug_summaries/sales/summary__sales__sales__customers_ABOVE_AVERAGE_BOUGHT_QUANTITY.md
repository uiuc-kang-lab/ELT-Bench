# Column Mismatch Summary

## Database: sales
## Table: sales__customers
## Column: ABOVE_AVERAGE_BOUGHT_QUANTITY

### Description
Set to 1 if the customer has bought more than the average quantity of all customers, 0 otherwise.

---

## Root Cause
**Wrong population for average calculation - SQL includes all customers (including those with 0 purchases) instead of only customers with purchases**

### Incorrect SQL Logic
```sql
customer_aggregates AS (
    SELECT
        CustomerID,
        FirstName,
        LastName,
        SUM(COALESCE(Quantity, 0)) as total_bought_quantity,
        ...
    FROM customer_sales
    GROUP BY CustomerID, FirstName, LastName
),

avg_quantity AS (
    SELECT AVG(total_bought_quantity) as avg_qty
    FROM customer_aggregates  -- Includes ALL customers (even those with 0 purchases)
)

SELECT
    ...
    CASE WHEN ca.total_bought_quantity > aq.avg_qty THEN 1 ELSE 0 END as above_average_bought_quantity,
FROM customer_aggregates ca
CROSS JOIN avg_quantity aq
```

### Correct SQL Logic
```sql
customer_aggregates AS (
    SELECT
        CustomerID,
        FirstName,
        LastName,
        SUM(COALESCE(Quantity, 0)) as total_bought_quantity,
        ...
    FROM customer_sales
    GROUP BY CustomerID, FirstName, LastName
),

avg_quantity AS (
    SELECT AVG(total_bought_quantity) as avg_qty
    FROM customer_aggregates
    WHERE total_bought_quantity > 0  -- Only include customers who made purchases
)

SELECT
    ...
    CASE WHEN ca.total_bought_quantity > aq.avg_qty THEN 1 ELSE 0 END as above_average_bought_quantity,
FROM customer_aggregates ca
CROSS JOIN avg_quantity aq
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: "average quantity of all customers" should be interpreted as customers who have actually made purchases
* **What the SQL actually computes**: Average over ALL customers including 19,192 customers with zero purchases, dramatically lowering the average

The difference in average calculation:
- **Current SQL (all customers)**: Average = 3,353,696,223 / 19,759 = 169,730.06
- **Ground Truth (non-zero only)**: Average = 3,353,696,223 / 567 = 5,914,808.15

This massive difference (35x higher threshold) means many customers with moderate purchases incorrectly get flagged as "above average" in the current implementation.

---

## Evidence

**Key comparison demonstrating the error:**

| CustomerID | Total Bought Quantity | Avg (all) | Avg (non-zero) | Wrong Flag | Correct Flag | Ground Truth |
| ---------- | -------------------- | --------- | -------------- | ---------- | ------------ | ------------ |
| 5 | 431,756 | 169,730 | 5,914,808 | 1 | 0 | 0 |
| 6 | 192,276 | 169,730 | 5,914,808 | 1 | 0 | 0 |
| 137 | 5,817,126 | 169,730 | 5,914,808 | 1 | 0 | 0 |
| 80 | 10,204,162 | 169,730 | 5,914,808 | 1 | 1 | 1 |

**Average calculation breakdown:**
- Total quantity purchased (all customers): 3,353,696,223
- Total customers: 19,759
- Customers with purchases: 567 (2.9%)
- Average including zeros: 169,730.06
- Average excluding zeros: 5,914,808.15

**Impact:**
* Current implementation: **19,557/19,759 matches (99.0%)**
* Corrected implementation: **19,759/19,759 matches (100%)**

---

## Result
**Correction needed**

Add a WHERE clause to filter out zero-quantity customers when calculating the average:
```sql
avg_quantity AS (
    SELECT AVG(total_bought_quantity) as avg_qty
    FROM customer_aggregates
    WHERE total_bought_quantity > 0
)
```
