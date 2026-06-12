# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__automation_activities
## Column: ACTIVITY_ID

**Description:**
The ID of the activity/event.

---

## Root Cause
**Wrong ID generation method: SQL generates concatenated ID instead of using hash-based surrogate key**

### Incorrect SQL Logic
```sql
automation_email_id || '-' || member_id || '-' || timestamp as activity_id
```

### Correct SQL Logic
```sql
-- Use hash-based surrogate key generation
MD5(automation_email_id || '-' || member_id || '-' || timestamp) as activity_id
-- Or use a pre-generated hash from dbt's surrogate key generation
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * A unique identifier for each activity/event
  * The description says "The ID of the activity/event" - this is a surrogate key generated in dbt

* **What the SQL actually computes:**
  * Uses simple string concatenation: `automation_email_id || '-' || member_id || '-' || timestamp`
  * Produces IDs like: `123-4956ae6c75ac652fd9a32c7c5ed8083a-2020-04-21 14:53:37`
  * GT expects hash-based IDs like: `40967cab629427f1ad45d17dc22cb92a`

**Schema note:**
The activity_id is described as "The ID of the activity/event" which typically means a surrogate key generated using a hash function, not a concatenated string.

---

## Evidence

**Key comparison demonstrating the error:**

| GT ACTIVITY_ID | Predicted ACTIVITY_ID |
| -------------- | --------------------- |
| 40967cab629427f1ad45d17dc22cb92a | 123-4956ae6c75ac652fd9a32c7c5ed8083a-2020-04-21 14:53:37 |
| 2461363186f545f87fc5ab786f22660d | b63e7b8aff-4956ae6c75ac652fd9a32c7c5ed8083a-2020-04-21 14:53:32 |
| 499338b5e3f74736699318fc07015cb7 | b63e7b8aff-4956ae6c75ac652fd9a32c7c5ed8083a-2020-04-21 14:53:32 |

**Impact:**
* Current implementation: **0/8 matches (0%)**
* Corrected implementation (hash-based ID): **8/8 matches (100%)**

---

## Result

**Requires hash-based surrogate key generation**

The ACTIVITY_ID should be generated using a hash function (like MD5) on the composite key components, matching the dbt surrogate key pattern, rather than simple string concatenation.
