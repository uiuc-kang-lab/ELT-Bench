# Column Mismatch Summary

## Database: movie_3
## Table: customers
## Column: AVG_AMOUNT_OF_MONEY_SPENT_ON_RENTAL

**Description:**
The average amount of money on a single film rental the customer has spent

---

## Root Cause
**SQL joins payment via rental_id, but GT averages payment.amount directly by customer_id (includes orphan payments)**

### Incorrect SQL Logic
```sql
customer_rental_stats AS (
    SELECT
        c.customer_id,
        ...
        AVG(p.amount) AS avg_amount_of_money_spent_on_rental,
        ...
    FROM {{ source('airbyte_schema', 'customer') }} c
    LEFT JOIN {{ source('airbyte_schema', 'rental') }} r ON c.customer_id = r.customer_id
    LEFT JOIN {{ source('airbyte_schema', 'payment') }} p ON r.rental_id = p.rental_id
    ...
    GROUP BY c.customer_id
)
```

### Correct SQL Logic
```sql
customer_payment_stats AS (
    SELECT
        customer_id,
        AVG(amount) AS avg_amount_of_money_spent_on_rental
    FROM {{ source('airbyte_schema', 'payment') }}
    GROUP BY customer_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "The average amount of money on a single film rental the customer has spent"
* **What the SQL computes**: Average of payments that have matching rental records (via rental_id join)
* **What the GT expects**: Average of ALL payments for the customer (directly from payment.customer_id)

The payment table has 5 records with rental_ids that don't exist in the rental table ("orphan payments"). When joining via rental_id, these payments are excluded from the average calculation. The GT includes all payments regardless of whether they have matching rental records.

---

## Evidence

**Key comparison demonstrating the error:**

| Customer ID | Payments (direct) | Payments (via rental join) | GT Avg | PRED Avg |
| ----------- | ----------------- | -------------------------- | ------ | -------- |
| 16 | 29 | 28 | 4.162414 | 4.240000 |
| 259 | 33 | 32 | 5.171818 | 5.271250 |
| 401 | 22 | 21 | 3.399091 | 3.513810 |
| 577 | 28 | 27 | 4.240000 | 4.360370 |

**Orphan payments (5 records):**
These payments have rental_ids that don't exist in the rental table:

| payment_id | customer_id | rental_id | amount | payment_date |
| ---------- | ----------- | --------- | ------ | ------------ |
| 424 | 16 | (missing) | varies | 2005-06-18 |
| 7011 | 259 | (missing) | varies | 2005-08-23 |
| 10840 | 401 | (missing) | varies | 2005-07-12 |
| 14675 | 546 | (missing) | varies | 2005-07-30 |
| 15458 | 577 | (missing) | varies | 2005-05-27 |

Note: Customer 546 doesn't show as a mismatch because the difference rounds to within tolerance.

**Impact:**
* Current implementation: **595/599 matches (99.3%)**
* Corrected implementation: **599/599 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Key insight:**
The GT calculates the average directly from the payment table using customer_id, without requiring a valid rental_id join. This includes all payments associated with a customer, even if the rental record is missing from the rental table (possibly due to data cleanup or other reasons).

**Affected customers (4 with visible mismatches + 1 within tolerance):**
- Customer 16: 1 extra payment included in GT average
- Customer 259: 1 extra payment included in GT average
- Customer 401: 1 extra payment included in GT average
- Customer 546: 1 extra payment included in GT average (within rounding tolerance)
- Customer 577: 1 extra payment included in GT average
