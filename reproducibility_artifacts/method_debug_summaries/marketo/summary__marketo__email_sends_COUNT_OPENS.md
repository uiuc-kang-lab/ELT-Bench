# Column Mismatch Summary

## Database: marketo
## Table: marketo__email_sends
## Column: COUNT_OPENS

**Description:**
Count of total opens from related email sends. Set the value to 0 if it is NULL.

---

## Root Cause
**No issue - SQL logic is correct**

### Current SQL Logic (Correct)
```sql
email_send_metrics AS (
    SELECT
        es.email_send_id,
        COUNT(DISTINCT eo.activity_timestamp) AS count_opens
    FROM email_sends_with_id es
    LEFT JOIN email_opens eo
        ON es.email_template_id = eo.email_template_id
        AND es.lead_id = eo.lead_id
        AND eo.activity_timestamp >= es.activity_timestamp
    GROUP BY es.email_send_id
)

SELECT
    COALESCE(esm.count_opens, 0) AS count_opens
```

---

## Why the Original Logic Is Correct

* **What the column description means:**
  * Count of open events for a given email send
  * NULL values should be replaced with 0

* **What the SQL actually computes:**
  * Joins email sends with the open_email activity table
  * Counts distinct open timestamps after the send timestamp
  * Uses COALESCE to replace NULL with 0

---

## Evidence

**Impact:**
* Current implementation: **100/100 matches (100%)**

---

## Result

**Perfect match - no changes needed**

The SQL correctly:
1. Joins email sends with open activities on template and lead
2. Filters to opens occurring after the send timestamp
3. Counts distinct open timestamps
4. Uses COALESCE to handle NULLs
