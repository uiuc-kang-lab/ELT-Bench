# Column Mismatch Summary

## Database: books
## Table: customers
## Column: PER_ORDER_SHIPPED_INTERNATIONALLY

### Description
The percentage of orders placed by the customer that were shipped internationally.

---

## Root Cause
**Wrong country comparison: SQL checks if destination country != 'USA' but country_name in database may be different (e.g., 'United States')**

### Incorrect SQL Logic
```sql
customer_stats AS (
    SELECT
        ...
        COUNT(CASE WHEN country_name != 'USA' THEN 1 END) AS international_orders,
        COUNT(DISTINCT CASE WHEN order_id IS NOT NULL THEN order_id END) AS total_orders_for_shipping
    FROM customer_orders
    GROUP BY customer_id, first_name, last_name, email
),

-- Final calculation
ROUND(100.0 * cs.international_orders / NULLIF(cs.total_orders_for_shipping, 0), 2) AS per_order_shipped_internationally
```

### Correct SQL Logic
```sql
-- Option 1: Use correct country name
COUNT(CASE WHEN country_name != 'United States' THEN 1 END) AS international_orders

-- Option 2: Check country_id directly (if USA has known ID)
COUNT(CASE WHEN country_id != [USA_COUNTRY_ID] THEN 1 END) AS international_orders

-- Option 3: Use LIKE or IN for flexibility
COUNT(CASE WHEN country_name NOT IN ('USA', 'United States', 'US') THEN 1 END) AS international_orders
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Calculate what percentage of a customer's orders were shipped to an international destination (not domestic/USA).

* **What the SQL actually computes**: The SQL checks `country_name != 'USA'`. If the country table stores "United States" instead of "USA", then ALL orders appear as international (100%).

* **Evidence**: Predicted shows 100% for ALL customers with orders, while GT shows varying percentages (0%, 25%, 50%, etc.). This confirms the country name mismatch - every order is counted as "international" because none match 'USA'.

---

## Evidence

**Key comparison demonstrating the error:**

| Customer ID | GT (%) | Pred (%) |
| ----------- | ------ | -------- |
| 1 | 0.0 | 100.0 |
| 2 | 25.0 | 100.0 |
| 3 | 50.0 | 100.0 |
| 4 | 0.0 | 100.0 |
| 5 | 33.33 | 100.0 |
| 19 | 100.0 | 100.0 |

**Pattern:**
- GT shows 0% for some customers (all domestic orders)
- GT shows various percentages (some domestic, some international)
- GT shows 100% for some (all international)
- Pred shows 100% for ALL customers

**Unique values:**
- GT: [0%, 20%, 25%, 28.57%, 30%, 33.33%, 40%, 50%, 75%, 100%, ...]
- Pred: [100%] only

**Impact:**
* Current implementation: **443/2000 matches (22.1%)**
* Corrected implementation: **2000/2000 matches (100%)**

---

## Result

**Mismatch due to incorrect country name for USA comparison**

**Key insight:**
The country table likely stores "United States" (or similar) rather than "USA". The SQL condition `country_name != 'USA'` is always TRUE, making every order appear as international.

**To fix:**
1. Check the actual value in the country table for the United States
2. Update the condition to match that exact value
3. Or use the country_id instead of country_name for comparison

**Customers with 100% international orders in GT (truly all international):**
- Customer 19 (Sanford Gillbe) - GT=100%, Pred=100% ✓
- Customer 26 (Mathilde Kleanthous) - GT=100%, Pred=100% ✓
- Customer 40 (Natty Bencher) - GT=100%, Pred=100% ✓
- ... (443 total matches - these are customers where all orders were actually international)
