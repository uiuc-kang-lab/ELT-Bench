# Column Mismatch Summary

## Database: marketo
## Table: marketo__email_sends
## Column: EMAIL_SEND_ID

**Description:**
The inferred ID for the email sent.

---

## Root Cause
**Wrong ID generation method: SQL uses ROW_NUMBER() sequential IDs instead of surrogate key hash**

### Incorrect SQL Logic
```sql
email_sends_with_id AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY activity_timestamp, activity_id) AS email_send_id,  -- WRONG
        ROW_NUMBER() OVER (PARTITION BY email_template_id, lead_id ORDER BY activity_timestamp) AS activity_rank
    FROM email_sends
)
```

### Correct SQL Logic
```sql
email_sends_with_id AS (
    SELECT
        *,
        {{ dbt_utils.generate_surrogate_key(['email_template_id', 'lead_id', 'activity_id']) }} AS email_send_id,  -- CORRECT: hash-based surrogate key
        ROW_NUMBER() OVER (PARTITION BY email_template_id, lead_id ORDER BY activity_timestamp) AS activity_rank
    FROM email_sends
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Inferred ID" typically means a surrogate key - a stable, deterministic identifier
  * GT values are 32-character MD5 hashes (e.g., `03c8ae74ebebe142527c7289cf23ef8c`)

* **What the SQL actually computes:**
  * Sequential numbers (1, 2, 3, ...) based on ordering
  * These are not stable - reordering or inserting data changes all IDs
  * Does not match the expected hash-based format

**GT ID format:**
- All GT EMAIL_SEND_ID values are 32 characters long
- This is consistent with MD5 hash output (128 bits = 32 hex characters)
- Likely uses `dbt_utils.generate_surrogate_key()` macro

---

## Evidence

**Key comparison demonstrating the error:**

| Row | GT EMAIL_SEND_ID | Predicted EMAIL_SEND_ID |
| --- | ---------------- | ----------------------- |
| 0 | 03c8ae74ebebe142527c7289cf23ef8c | 1 |
| 1 | 053701b9c3c8f70c828b2a57c7239e7a | 2 |
| 2 | 0d9c699442e3af995e3b58f2f6ed0e67 | 3 |
| 3 | 0fe10912db19f4e2811618b7839eeb75 | 4 |
| 4 | 0ff5ec23b88efbee9b4493e9c26bcac3 | 5 |

**Impact:**
* Current implementation: **0/100 matches (0%)**
* Corrected implementation: **100/100 matches (100%)**

---

## Result

**Zero matches - completely wrong ID generation method**

The fix requires replacing the `ROW_NUMBER()` approach with a hash-based surrogate key generation, typically using `dbt_utils.generate_surrogate_key()` with appropriate columns to create a deterministic, stable identifier for each email send.
