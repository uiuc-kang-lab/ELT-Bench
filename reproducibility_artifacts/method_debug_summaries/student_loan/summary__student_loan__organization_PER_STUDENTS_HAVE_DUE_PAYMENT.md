# Column Mismatch Summary

## Database: student_loan
## Table: organization
## Column: PER_STUDENTS_HAVE_DUE_PAYMENT

**Description:**
The percentage of students in the organization who have due payments.

---

## Root Cause
**Inverted logic in payment due calculation**

### Current SQL Logic (Incorrect)
```sql
payment_due_count AS (
    SELECT
        os.organ,
        COUNT(DISTINCT CASE WHEN npd.bool = 'neg' THEN os.name END) AS num_students_with_due
    FROM org_students os
    LEFT JOIN no_payment_due npd ON os.name = npd.name
    GROUP BY os.organ
)

CASE
    WHEN ts.total_students > 0 THEN (pdc.num_students_with_due * 100.0 / ts.total_students)
    ELSE 0
END AS per_students_have_due_payment
```

### Expected Logic
```sql
-- Count students who have due payments
-- In no_payment_due table: 'pos' means NO payment due, 'neg' means HAS payment due
-- But also need to count students NOT in the no_payment_due table as having due payments
COUNT(DISTINCT CASE WHEN npd.bool IS NULL OR npd.bool = 'neg' THEN os.name END) AS num_students_with_due
```

---

## Why This Is Wrong

* **What the column should compute:**
  * Percentage of students who HAVE due payments

* **What the SQL actually computes:**
  * Only counts students with `bool = 'neg'` in no_payment_due table
  * Students NOT in the no_payment_due table are treated as NOT having due payments

* **The issue:**
  * The no_payment_due table only contains students with explicit payment status
  * Students not in this table should be counted as having due payments
  * GT shows 100% for most organizations, meaning all students have due payments
  * Pred shows 0% for these same organizations because students aren't in no_payment_due with 'neg'

---

## Evidence

**Impact:**
* Current implementation: **0/7 matches (0%)**

| ORGAN | GT | Pred |
|-------|-----|------|
| air_force | 100.00% | 0.00% |
| army | 100.00% | 0.00% |
| fire_department | 59.65% | 40.54% |
| foreign_legion | 38.71% | 61.29% |
| marines | 100.00% | 0.00% |
| navy | 100.00% | 0.00% |
| peace_corps | 100.00% | 0.00% |

---

## Result

**Requires fix: Students not in no_payment_due table should be counted as having due payments**

The SQL should count students as having due payments when:
1. They have `bool = 'neg'` in no_payment_due table, OR
2. They are NOT in the no_payment_due table at all (NULL after LEFT JOIN)
