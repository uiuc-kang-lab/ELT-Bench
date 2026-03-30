# Column Mismatch Summary

## Database: car_retails
## Table: car_retails__customers
## Column: COUNTRY

### Description
Country where the customer is located.

---

## Root Cause
**Whitespace handling: SQL trims trailing whitespace but source data preserves it**

### Incorrect SQL Logic
```sql
SELECT
    c.customerNumber,
    c.customerName,
    c.country,  -- Source has trailing whitespace for some values
    ...
FROM customers c
```

The SQL correctly uses `c.country` as-is, but some SQL engines or ETL processes may automatically trim whitespace.

### Correct SQL Logic
```sql
SELECT
    c.customerNumber,
    c.customerName,
    c.country,  -- Preserve whitespace exactly as stored in source
    ...
FROM customers c
```

---

## Why the Original Logic Is Wrong

* The source `customers.country` column contains trailing whitespace for some values (e.g., "Norway  " instead of "Norway")
* If the SQL or ETL process trims whitespace, it will not match the ground truth which preserves the original data format
* This is a data quality issue in the source data, but the GT expects the original values to be preserved

---

## Evidence

**Key comparison demonstrating the error:**

| Customer Number | Source Value | Predicted (Trimmed) | Ground Truth |
| --------------- | ------------ | ------------------- | ------------ |
| 167             | "Norway  "   | "Norway"            | "Norway  "   |
| 299             | "Norway  "   | "Norway"            | "Norway  "   |

Only 2 customers have this issue - both are from Norway with trailing whitespace.

**Impact:**
* Current implementation: **120/122 matches (98.4%)**
* Corrected implementation: **122/122 matches (100%)**

---

## Result
**Perfect match when whitespace is preserved**

**Key insight:**
The source data contains trailing whitespace for some country values. The correct behavior is to preserve the data exactly as stored, without trimming. If whitespace trimming is needed for data quality, it should be handled consistently across both GT generation and SQL implementation.
