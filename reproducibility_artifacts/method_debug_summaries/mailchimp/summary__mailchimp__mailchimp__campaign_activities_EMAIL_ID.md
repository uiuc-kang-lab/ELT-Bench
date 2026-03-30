# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaign_activities
## Column: EMAIL_ID

**Description:**
The ID of the email sent. Surrogate key generated in dbt from 'campaign_id' and 'member_id'.

---

## Root Cause
**Wrong ID generation method: SQL uses concatenation instead of hash-based surrogate key**

### Incorrect SQL Logic
```sql
campaign_id || '-' || member_id AS email_id
```

### Correct SQL Logic
```sql
-- Use hash-based surrogate key (MD5 or similar)
MD5(campaign_id || '-' || member_id) AS email_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Surrogate key generated in dbt from 'campaign_id' and 'member_id'"
  * dbt typically generates surrogate keys using hash functions

* **What the SQL actually computes:**
  * Simple concatenation: `c2b4c1c0d9-31d6eef7ddb994d81380735289af2dfb`
  * GT expects hash: `f9fca55a78d58b4b7ea4a73e0c0e8d46`

---

## Evidence

**Key comparison demonstrating the error:**

| GT EMAIL_ID | Predicted EMAIL_ID |
| ----------- | ------------------ |
| f9fca55a78d58b4b7ea4a73e0c0e8d46 | c2b4c1c0d9-31d6eef7ddb994d81380735289af2dfb |
| be238184d94f95824a3af1e132f0ac8f | c2b4c1c0d9-37cc8cad6a75f018d69632984d8caf38 |
| 9e64bd6448e2b1b500c3771f0e5172c2 | c2b4c1c0d9-c6de178b4b5cac03e73f9d787b352f15 |

**Impact:**
* Current implementation: **0/17 matches (0%)**
* Corrected implementation (hash-based): **17/17 matches (100%)**

---

## Result

**Requires hash-based surrogate key generation**

The description explicitly states this is a surrogate key - should use MD5 hash.
