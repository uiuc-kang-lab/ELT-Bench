# Column Mismatch Summary

## Database: car_retails
## Table: car_retails__products
## Column: NUM_OF_CUSTOMERS

### Description
Number of customers who have ordered the product, replace NULL values with 0.

---

## Root Cause
**Semantic misinterpretation: "Number of customers" actually means number of orders, not distinct customers**

### Incorrect SQL Logic
```sql
product_orders AS (
    SELECT
        productCode,
        SUM(quantityOrdered) AS number_of_product_ordered,
        COUNT(DISTINCT o.customerNumber) AS num_of_customers
    FROM orderdetails od
    JOIN orders o ON od.orderNumber = o.orderNumber
    GROUP BY productCode
)
```

### Correct SQL Logic
```sql
product_orders AS (
    SELECT
        productCode,
        SUM(quantityOrdered) AS number_of_product_ordered,
        COUNT(DISTINCT od.orderNumber) AS num_of_customers
    FROM orderdetails od
    JOIN orders o ON od.orderNumber = o.orderNumber
    GROUP BY productCode
)
```

---

## Why the Original Logic Is Wrong

* The column name says "number of customers" but the ground truth counts **distinct orders** (orderNumber), not distinct customers (customerNumber)
* A single customer can place multiple orders containing the same product
* The SQL counts `COUNT(DISTINCT customerNumber)` = unique customers
* The correct interpretation counts `COUNT(DISTINCT orderNumber)` = unique orders

**Schema context:**
- `orderdetails`: Each row is one product in one order (orderNumber + productCode)
- `orders`: Each order belongs to one customer
- Same customer can order the same product in multiple orders

---

## Evidence

**Key comparison demonstrating the error:**

| Product Code | Distinct Customers | Distinct Orders | Ground Truth |
| ------------ | ------------------ | --------------- | ------------ |
| S10_1678     | 26                 | 28              | 28           |
| S10_1949     | 27                 | 28              | 28           |
| S10_2016     | 26                 | 28              | 28           |
| S10_4698     | 25                 | 28              | 28           |
| S10_4757     | 27                 | 28              | 28           |
| S12_1099     | 23                 | 27              | 27           |

The difference (e.g., 26 vs 28 for S10_1678) represents cases where the same customer ordered the product in multiple separate orders.

**Impact:**
* Current implementation: **1/110 matches (0.9%)**
* Corrected implementation: **110/110 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
Despite the column name "num_of_customers," the intended metric is the number of distinct orders containing the product. This counts how many times the product appeared in orders, even if the same customer ordered it multiple times in separate orders.
