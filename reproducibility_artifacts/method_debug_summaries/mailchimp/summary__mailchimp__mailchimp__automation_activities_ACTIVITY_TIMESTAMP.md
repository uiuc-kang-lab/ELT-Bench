# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__automation_activities
## Column: ACTIVITY_TIMESTAMP

**Description:**
The timestamp when the activity occurred.

---

## Root Cause
**Row ordering mismatch: Data is in different order between GT and predicted, but the values are correct when matched by composite key**

### Incorrect SQL Logic
```sql
-- No actual logic error - the issue is row ordering
SELECT
    timestamp as activity_timestamp,
    ...
FROM automation_recipient_activity
```

### Correct SQL Logic
```sql
-- Same logic with explicit ordering
SELECT
    timestamp as activity_timestamp,
    ...
FROM automation_recipient_activity
ORDER BY automation_email_id, member_id, timestamp
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The timestamp of when the activity occurred, directly from source

* **What the SQL actually computes:**
  * The SQL correctly reads the timestamp column
  * The mismatch is due to row ordering differences
  * The same timestamps exist in both datasets, just at different row positions

---

## Evidence

**Key comparison demonstrating the ordering issue:**

| Row | GT Timestamp | Pred Timestamp |
| --- | ------------ | -------------- |
| 0 | 2020-04-21 14:53:37 | 2020-04-21 14:53:37 |
| 1 | 2020-04-21 14:52:06 | 2020-04-21 14:53:32 |
| 2 | 2020-04-21 14:52:06 | 2020-04-21 14:53:32 |
| 3 | 2020-04-21 14:52:11 | 2020-04-21 14:53:34 |

**Impact:**
* Position-based comparison: **1/8 matches (12.5%)**
* Key-based comparison: **8/8 matches (100%)**

---

## Result

**This is a row ordering issue, not a SQL logic error**

The ACTIVITY_TIMESTAMP values are correct when compared using proper key matching.
