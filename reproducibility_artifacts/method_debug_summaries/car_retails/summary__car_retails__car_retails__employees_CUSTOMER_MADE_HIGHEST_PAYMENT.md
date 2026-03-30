# Column Mismatch Summary

## Database: car_retails
## Table: car_retails__employees
## Column: CUSTOMER_MADE_HIGHEST_PAYMENT

### Description
Name of the customer who made the highest payment to the employee, with ties broken by the descending order of the customer name.

---

## Root Cause
**Aggregation interpretation: "Highest payment" means the single largest payment transaction, not the sum of all payments**

### Incorrect SQL Logic
```sql
highest_payment_customer AS (
    SELECT
        c.salesRepEmployeeNumber,
        c.customerName,
        SUM(pay.amount) AS total_payment,
        ROW_NUMBER() OVER (
            PARTITION BY c.salesRepEmployeeNumber
            ORDER BY SUM(pay.amount) DESC, c.customerName DESC
        ) AS rn
    FROM customers c
    JOIN payments pay ON c.customerNumber = pay.customerNumber
    WHERE c.salesRepEmployeeNumber IS NOT NULL
    GROUP BY c.salesRepEmployeeNumber, c.customerName
)
```

### Correct SQL Logic
```sql
highest_payment_customer AS (
    SELECT
        c.salesRepEmployeeNumber,
        c.customerName,
        pay.amount AS payment_amount,
        ROW_NUMBER() OVER (
            PARTITION BY c.salesRepEmployeeNumber
            ORDER BY pay.amount DESC, c.customerName DESC
        ) AS rn
    FROM customers c
    JOIN payments pay ON c.customerNumber = pay.customerNumber
    WHERE c.salesRepEmployeeNumber IS NOT NULL
)
```

---

## Why the Original Logic Is Wrong

* The SQL groups by `(salesRepEmployeeNumber, customerName)` and calculates `SUM(amount)` per customer
* This finds the customer who paid the most in total across all their payments
* The correct interpretation: find the single payment record with the highest amount
* "Highest payment" = maximum individual payment transaction, not aggregated total

**Key distinction:**
- Wrong: Total payments made by a customer to the employee's accounts
- Correct: The single largest payment transaction made by any customer

---

## Evidence

**Key comparison demonstrating the error:**

| Employee | Wrong (Sum Payments) | Wrong Customer | Correct (Max Single) | Correct Customer | GT |
| -------- | -------------------- | -------------- | -------------------- | ---------------- | -- |
| 1166     | 93,803.30            | Toys4GrownUps.com | 80,375.24 | Collectable Mini Designs Co. | Collectable Mini Designs Co. |
| 1188     | 101,872.52           | Mini Creations Ltd. | 59,265.14 | Diecast Collectables | Diecast Collectables |
| 1337     | 130,305.35           | Saveley & Henriot | 51,209.58 | La Corne D'abondance | La Corne D'abondance |
| 1401     | 53,959.21            | Rovelli Gifts | 53,959.21 | Danish Wholesale Imports | Danish Wholesale Imports |

**Example for Employee 1166:**
- "Toys4GrownUps.com" has the highest total payments ($93,803.30 summed)
- But "Collectable Mini Designs Co." made the single largest payment ($80,375.24 in one transaction)
- GT expects the customer with the single largest payment

**Impact:**
* Current implementation: **16/23 matches (69.6%)**
* Corrected implementation: **23/23 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The phrase "highest payment" refers to the maximum individual payment transaction (amount), not the sum of all payments from a customer. This identifies which single payment transaction was the largest for each employee's customer base.
