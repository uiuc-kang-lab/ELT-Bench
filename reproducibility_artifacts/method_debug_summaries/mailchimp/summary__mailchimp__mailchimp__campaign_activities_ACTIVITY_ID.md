# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__campaign_activities
## Column: ACTIVITY_ID

**Description:**
The ID of the activity/event.

---

## Root Cause
**Wrong ID generation method: SQL generates concatenated ID instead of hash-based surrogate key**

### Incorrect SQL Logic
```sql
campaign_id || '-' || member_id || '-' || timestamp AS activity_id
```

### Correct SQL Logic
```sql
-- Use hash-based surrogate key (MD5 or similar)
MD5(campaign_id || '-' || member_id || '-' || timestamp) AS activity_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * A unique identifier for each activity/event
  * This is a surrogate key generated using a hash function

* **What the SQL actually computes:**
  * Simple string concatenation produces readable but non-standard IDs
  * GT expects 32-character hexadecimal hash IDs

---

## Evidence

**Key comparison demonstrating the error:**

| GT ACTIVITY_ID | Predicted ACTIVITY_ID |
| -------------- | --------------------- |
| 43dbecedcf8616a8f55c499244ea59ba | c2b4c1c0d9-31d6eef7ddb994d81380735289af2dfb-2019-11-27 17:01:55.000 |
| fc9bdacbb3182bcd1bd58fd43886c2ef | c2b4c1c0d9-37cc8cad6a75f018d69632984d8caf38-2019-11-27 17:34:16.000 |
| 18553e89465bc896aed1cfdce5ef1de3 | c2b4c1c0d9-c6de178b4b5cac03e73f9d787b352f15-2019-11-27 17:44:09.000 |

**Impact:**
* Current implementation: **0/17 matches (0%)**
* Corrected implementation (hash-based): **17/17 matches (100%)**

---

## Result

**Requires hash-based surrogate key generation**

The ACTIVITY_ID should be generated using MD5 or similar hash function on the composite key.
