# Column Mismatch Summary

## Database: mailchimp
## Table: mailchimp__automation_activities
## Column: MEMBER_ID

**Description:**
The ID of the member the activity relates to.

---

## Root Cause
**Row ordering mismatch: Data is in different order between GT and predicted, but the values are correct when matched by composite key**

### Incorrect SQL Logic
```sql
-- No actual logic error - the issue is row ordering/comparison methodology
SELECT
    member_id,
    ...
FROM automation_recipient_activity
-- Rows returned in undefined order
```

### Correct SQL Logic
```sql
-- Same logic with explicit ordering for consistent comparison
SELECT
    member_id,
    ...
FROM automation_recipient_activity
ORDER BY automation_email_id, member_id, timestamp
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The member_id should be directly from the source automation_recipient_activity table

* **What the SQL actually computes:**
  * The SQL correctly reads the member_id column
  * The mismatch is due to row ordering differences
  * Both GT and predicted contain the same set of member_ids, just in different row positions

**Evidence of ordering issue:**
- GT row 1 has member_id `4d1bf0aa67...`
- Pred row 1 has member_id `4956ae6c75...`
- Both member_ids exist in both datasets

---

## Evidence

**Key comparison demonstrating the ordering issue:**

| Row | GT Member_ID | Pred Member_ID | Match |
| --- | ------------ | -------------- | ----- |
| 0 | 4956ae6c75... | 4956ae6c75... | Yes |
| 1 | 4d1bf0aa67... | 4956ae6c75... | No |
| 2 | 4d1bf0aa67... | 4956ae6c75... | No |
| 5 | 4956ae6c75... | 4d1bf0aa67... | No |

**Impact:**
* Position-based comparison: **2/8 matches (25%)**
* Key-based comparison (using composite key): **8/8 matches (100%)**

---

## Result

**This is a row ordering issue, not a SQL logic error**

The MEMBER_ID values are correct. The comparison methodology should use composite key matching rather than row position matching.
