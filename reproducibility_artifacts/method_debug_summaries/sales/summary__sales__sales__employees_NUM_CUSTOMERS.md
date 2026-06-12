# Column Mismatch Summary

## Database: sales
## Table: sales__employees
## Column: NUM_CUSTOMERS

### Description
The number of customers the employee has served, replace NULL values with 0.

---

## Root Cause
**Misinterpretation of "num_customers" - SQL counts distinct customers when it should count total sales transactions**

### Incorrect SQL Logic
```sql
employee_aggregates AS (
    SELECT
        EmployeeID,
        FirstName,
        LastName,
        COUNT(DISTINCT CASE WHEN CustomerID IS NOT NULL THEN CustomerID END) as num_customers,
        ...
    FROM employee_sales
    GROUP BY EmployeeID, FirstName, LastName
)
```

### Correct SQL Logic
```sql
employee_aggregates AS (
    SELECT
        EmployeeID,
        FirstName,
        LastName,
        COUNT(CASE WHEN SalesID IS NOT NULL THEN SalesID END) as num_customers,
        ...
    FROM employee_sales
    GROUP BY EmployeeID, FirstName, LastName
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Based on ground truth data, "num_customers" refers to the total number of sales transactions (customer interactions), not the count of unique customers
* **What the SQL actually computes**: COUNT(DISTINCT CustomerID) - the number of unique customers served

The column name is semantically ambiguous. In this context, "customer" appears to refer to each sales transaction (customer interaction), not unique individuals. The ground truth shows NUM_CUSTOMERS equals NUM_SALES for every employee, confirming this interpretation.

---

## Evidence

**Key comparison demonstrating the error:**

| EmployeeID | FirstName | COUNT(SalesID) | COUNT(DISTINCT CustomerID) | Ground Truth |
| ---------- | --------- | -------------- | -------------------------- | ------------ |
| 1 | Abraham | 505,147 | 108 | 505,147 |
| 10 | Sheryl | 302,469 | 70 | 302,469 |
| 11 | Livia | 274,913 | 75 | 274,913 |
| 12 | Charlene | 292,271 | 79 | 292,271 |
| 13 | Stearns | 257,932 | 85 | 257,932 |

**Analysis:**
- Ground truth NUM_CUSTOMERS = NUM_SALES for all 22 employees
- COUNT(SalesID) matches GT: 22/22 (100%)
- COUNT(DISTINCT CustomerID) matches GT: 0/22 (0%)

**Impact:**
* Current implementation: **0/22 matches (0%)**
* Corrected implementation: **22/22 matches (100%)**

---

## Result
**Correction needed**

Replace `COUNT(DISTINCT CASE WHEN CustomerID IS NOT NULL THEN CustomerID END)` with `COUNT(CASE WHEN SalesID IS NOT NULL THEN SalesID END)` or simply `COUNT(SalesID)` to count total sales transactions per employee.
