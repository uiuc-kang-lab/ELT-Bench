# Column Mismatch Summary

## Database: student_loan
## Table: students
## Column: FEMALE_AND_NO_DUE_PAYMENTS

**Description:**
Flag indicating if the student is female AND has no due payments (1=yes, 0=no).

---

## Root Cause
**Inverted payment due logic - treating 'pos' as having due payment instead of no due payment**

### Current SQL Logic (Incorrect)
```sql
payment_info AS (
    SELECT
        name,
        CASE WHEN bool = 'pos' THEN 0 ELSE 1 END AS has_due_payment
    FROM no_payment_due
)

CASE
    WHEN g.gender = 'Female' AND COALESCE(pay.has_due_payment, 0) = 0 THEN 1
    ELSE 0
END AS female_and_no_due_payments
```

### Expected Logic
```sql
-- 'pos' in no_payment_due means NO payment due (positive = good)
-- 'neg' means HAS payment due (negative = bad)
-- Students NOT in no_payment_due table have due payments

payment_info AS (
    SELECT
        name,
        CASE WHEN bool = 'pos' THEN 1 ELSE 0 END AS no_due_payment  -- 1 means no due payment
    FROM no_payment_due
)

CASE
    WHEN g.gender = 'F' AND COALESCE(pay.no_due_payment, 0) = 1 THEN 1
    ELSE 0
END AS female_and_no_due_payments
```

---

## Why This Is Wrong

* **What the column should compute:**
  * 1 if student is Female AND has no due payments
  * 0 otherwise

* **What the SQL actually computes:**
  * Interprets 'pos' as having due payment (wrong - 'pos' means positive/good = no due payment)
  * Also affected by gender format issue ('Female' vs 'F')

* **The issue:**
  * In no_payment_due table: 'pos' = no payment due, 'neg' = has payment due
  * Current logic inverts this meaning
  * Combined with the gender format issue, produces many mismatches

---

## Evidence

**Impact:**
* Current implementation: **497/1000 matches (49.70%)**

Sample mismatches:
| NAME | GT | Pred |
|------|-----|------|
| student10 | 1 | 0 |
| student100 | 0 | 1 |
| student1000 | 0 | 1 |
| student104 | 0 | 1 |
| student107 | 1 | 0 |

---

## Result

**Requires fix: Correct the payment due interpretation and gender format**

1. 'pos' in no_payment_due means NO due payment (positive outcome)
2. 'neg' in no_payment_due means HAS due payment (negative outcome)
3. Students not in no_payment_due table should be treated as having due payments
4. Gender check should use 'F' instead of 'Female'
