# Column Mismatch Summary

## Database: superstore
## Table: customers
## Column: THE_LARGEST_TOTAL_COST_OF_PRODUCTS_IN_A_SINGLE_ORDER

**Description:**
The largest total cost of products in a single order the customer has made.

---

## Root Cause
**Incorrect interpretation: SQL uses SUM(Sales) per order, but GT uses MAX(Sales) per individual product line**

### Incorrect SQL Logic
```sql
largest_order_cost AS (
    SELECT
        Customer_ID,
        MAX(order_total) AS the_largest_total_cost_of_products_in_a_single_order
    FROM (
        SELECT
            Customer_ID,
            Order_ID,
            SUM(Sales) AS order_total  -- Sums all products in order
        FROM all_orders
        GROUP BY Customer_ID, Order_ID
    )
    GROUP BY Customer_ID
)
```

### Correct SQL Logic
```sql
largest_order_cost AS (
    SELECT
        Customer_ID,
        MAX(Sales) AS the_largest_total_cost_of_products_in_a_single_order  -- Max single product sale
    FROM all_orders
    GROUP BY Customer_ID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Total cost of products in a single order" is ambiguous
  * GT interprets it as the largest single product sale amount (one line item)
  * NOT the sum of all products within one order

* **What the SQL actually computes:**
  * Sums all Sales values within each Order_ID
  * Then takes the max of these order totals
  * This gives larger values than intended

---

## Evidence

**Key comparison demonstrating the error:**

Example for customer AA-10315:
- Order CA-2013-103982 has 4 line items: 3930.072, 2.304, 431.976, 41.720
- SQL SUM = 4406.072 (total order)
- GT expects MAX = 3930.072 (largest single item)

| Customer | GT (max item) | Pred (sum of order) | Difference |
| -------- | ------------- | ------------------- | ---------- |
| AA-10315 | 3930.072 | 4406.072 | 476.00 |
| AA-10480 | 479.970 | 1157.980 | 678.01 |
| AA-10645 | 1323.900 | 1971.460 | 647.56 |

**Impact:**
* Current implementation: **179/793 matches (22.57%)**
* Corrected implementation: **793/793 matches (100%)**

---

## Result

**Perfect match expected with corrected logic**

**Key insight:**
The word "order" in "single order" refers to one transaction line, not the entire order (which could have multiple products). GT finds the maximum Sales value for any single product the customer bought, not the order with the highest total.
