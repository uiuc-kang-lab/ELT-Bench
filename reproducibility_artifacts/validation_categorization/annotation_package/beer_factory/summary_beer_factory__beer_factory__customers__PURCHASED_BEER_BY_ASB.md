# SQL Column Debugging Summary

## Database: beer_factory
## Table: beer_factory__customers
## Column: PURCHASED_BEER_BY_ASB

**Description:**
set to 1 if the customer has purchased at least one root beer produced by AJ Stephans Beverages, otherwise, set to 0

---

## Root Cause
**Wrong brand name in SQL query - uses 'AJ Stephans Beverages' but the actual brand name in the database is 'A.J. Stephans'**

### Incorrect SQL Logic
```sql
customer_purchases AS (
    SELECT
        t.CustomerID,
        MAX(CASE WHEN rb.brandname = 'AJ Stephans Beverages' THEN 1 ELSE 0 END) as purchased_beer_by_ASB,
        ...
    FROM transactions t
    JOIN rootbeer r ON t.RootBeerID = r.RootBeerID
    JOIN rootbeerbrand rb ON r.BrandID = rb.brandid
    GROUP BY t.CustomerID
)
```

### Correct SQL Logic
```sql
customer_purchases AS (
    SELECT
        t.CustomerID,
        MAX(CASE WHEN rb.brandname = 'A.J. Stephans' THEN 1 ELSE 0 END) as purchased_beer_by_ASB,
        ...
    FROM transactions t
    JOIN rootbeer r ON t.RootBeerID = r.RootBeerID
    JOIN rootbeerbrand rb ON r.BrandID = rb.brandid
    GROUP BY t.CustomerID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** Flag customers who have purchased any root beer from the brand "AJ Stephans Beverages"
* **What the SQL actually computes:** The SQL searches for `brandname = 'AJ Stephans Beverages'` which returns 0 matches because the actual brand name in the `rootbeerbrand` table is `'A.J. Stephans'` (with periods and different formatting)

The brand name mismatch causes all comparisons to fail:
- SQL searches for: `'AJ Stephans Beverages'`
- Actual brand name: `'A.J. Stephans'` (BrandID: 10002)

Since no brand matches the incorrect name, `MAX(CASE WHEN ... THEN 1 ELSE 0 END)` always returns 0 for all customers.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Value |
| ------ | ----- |
| Total customers | 554 |
| GT with PURCHASED_BEER_BY_ASB=1 | 220 |
| Pred with PURCHASED_BEER_BY_ASB=1 | 0 |
| Positional match | 334/554 (60.3%) |
| Semantic match (by CUSTOMER_ID) | 334/554 (60.3%) |

**Mismatch breakdown:**
- GT=1, Pred=0 (false negatives): 220 customers
- GT=0, Pred=1 (false positives): 0 customers

**Sample mismatches:**

| CUSTOMER_ID | GT Value | Pred Value |
| ----------- | -------- | ---------- |
| 103508 | 1 | 0 |
| 110363 | 1 | 0 |
| 111991 | 1 | 0 |
| 112690 | 1 | 0 |
| 116690 | 1 | 0 |

**Impact:**
* Current implementation: **334/554 matches (60.3%)**
* Corrected implementation: **554/554 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Customers where `PURCHASED_BEER_BY_ASB = 1`:**
220 customers who have purchased at least one root beer from the 'A.J. Stephans' brand (BrandID: 10002).
