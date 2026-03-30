# Column Mismatch Summary

## Database: financial
## Table: clients
## Column: NUM_WITHDRAWALS_IN_CASH_TRANSACTIONS

**Description:**
The number of withdrawals in cash transactions by the client, replace NULL values with 0.

---

## Root Cause
**Over-restrictive filter: SQL uses `type='VYDAJ' AND operation='VYBER'` when only `operation='VYBER'` is needed to identify cash withdrawals**

### Incorrect SQL Logic
```sql
withdrawal_stats AS (
    SELECT
        d.client_id,
        COUNT(CASE WHEN t.type = 'VYDAJ' AND t.operation = 'VYBER' THEN 1 END) AS num_withdrawals_in_cash_transactions
    FROM {{ source('airbyte_schema', 'disp') }} d
    JOIN {{ source('airbyte_schema', 'trans') }} t ON d.account_id = t.account_id
    GROUP BY d.client_id
)
```

### Correct SQL Logic
```sql
withdrawal_stats AS (
    SELECT
        d.client_id,
        COUNT(CASE WHEN t.operation = 'VYBER' THEN 1 END) AS num_withdrawals_in_cash_transactions
    FROM {{ source('airbyte_schema', 'disp') }} d
    JOIN {{ source('airbyte_schema', 'trans') }} t ON d.account_id = t.account_id
    GROUP BY d.client_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Count all cash withdrawal transactions for each client
  * The `operation` field in the trans table indicates the transaction operation type
  * `operation='VYBER'` means "cash withdrawal" in Czech

* **What the SQL actually computes:**
  * Filters transactions by BOTH `type='VYDAJ'` (expense) AND `operation='VYBER'` (cash withdrawal)
  * This is overly restrictive because cash withdrawals can occur with different transaction types
  * The `type` field indicates debit/credit direction, not the nature of the transaction

**Schema analysis:**
- `trans.type` values: VYDAJ (634,571 records), PRIJEM (405,083 records), VYBER (16,666 records)
- `trans.operation` values: VYBER (434,918 records), PREVOD NA UCET (208,283 records), etc.
- Note: 'VYBER' appears in both `type` and `operation` columns with different meanings
- In `type`: 'VYBER' is one of three transaction direction types
- In `operation`: 'VYBER' specifically means "cash withdrawal"

---

## Evidence

**Key comparison demonstrating the error:**

| Client ID | Wrong Logic (type='VYDAJ' AND operation='VYBER') | Correct Logic (operation='VYBER' only) | Ground Truth |
| --------- | ------------------------------------------------ | -------------------------------------- | ------------ |
| 2 | 216 | 237 | 237 |
| 3 | 216 | 237 | 237 |
| 4 | 127 | 138 | 138 |
| 5 | 127 | 138 | 138 |
| 6 | 50 | 59 | 59 |

**Transaction breakdown for Client 2:**
- Total transactions: 237 with `operation='VYBER'`
- Of those, 216 have `type='VYDAJ'`
- The remaining 21 have other type values but are still cash withdrawals

**Impact:**
* Current implementation: **4029/5369 matches (75.1%)**
* Corrected implementation: **5369/5369 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "withdrawals in cash transactions" refers specifically to the `operation` field value 'VYBER' (cash withdrawal), not to a combination of transaction type and operation. The `type` field indicates the direction of money flow (VYDAJ=expense, PRIJEM=income), while `operation` indicates how the transaction was performed (VYBER=cash withdrawal, PREVOD NA UCET=bank transfer, etc.).

**Test results from all interpretations:**
| Option | Filter Logic | Match Rate |
| ------ | ------------ | ---------- |
| Option 1 (Current) | type='VYDAJ' AND operation='VYBER' | 75.1% |
| Option 2 (Correct) | operation='VYBER' only | 100% |
| Option 3 | type='VYDAJ' only | 11.8% |
| Option 4 | operation contains 'VYBER' | 100% |
| Option 5 | type='PRIJEM' AND operation='VYBER' | 0% |
