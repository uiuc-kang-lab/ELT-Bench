# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaign_recipients
## Column: EMAIL_ID

**Description:**
The ID of the email sent. Surrogate key generated in dbt from 'campaign_id' and 'member_id'.

---

## Root Cause
**Wrong ID generation method: SQL uses concatenation instead of hash-based surrogate key**

### Incorrect SQL Logic
```sql
cr.campaign_id || '-' || cr.member_id AS email_id
```

### Correct SQL Logic
```sql
MD5(cr.campaign_id || '-' || cr.member_id) AS email_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "Surrogate key generated in dbt from 'campaign_id' and 'member_id'"
  * dbt surrogate keys use hash functions

* **What the SQL actually computes:**
  * Concatenation: `c2b4c1c0d9-001ab89f92fa8197d3f426cc6987b997`
  * GT expects hash: `cc6cfd3941015f9dfe44924689f68fd4`

---

## Evidence

**Key comparison demonstrating the error:**

| GT EMAIL_ID | Predicted EMAIL_ID |
| ----------- | ------------------ |
| cc6cfd3941015f9dfe44924689f68fd4 | c2b4c1c0d9-001ab89f92fa8197d3f426cc6987b997 |
| 511429cdb377c8c1890409aeb542a8c3 | c2b4c1c0d9-09be851d30b8958f7de29f22e8bed310 |
| f9fca55a78d58b4b7ea4a73e0c0e8d46 | c2b4c1c0d9-31d6eef7ddb994d81380735289af2dfb |

**Impact:**
* Current implementation: **0/10 matches (0%)**
* Corrected implementation (hash-based): **10/10 matches (100%)**

---

## Result

**Requires hash-based surrogate key generation**
