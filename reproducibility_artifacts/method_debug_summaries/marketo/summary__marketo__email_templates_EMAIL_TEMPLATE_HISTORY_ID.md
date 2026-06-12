# Column Mismatch Summary

## Database: marketo
## Table: marketo__email_templates
## Column: EMAIL_TEMPLATE_HISTORY_ID

**Description:**
ID of the version of the email template.

---

## Root Cause
**Incorrect ID generation: SQL uses email_template_id as history_id, but GT uses a hash identifier**

### Incorrect SQL Logic
```sql
email_template_history AS (
    SELECT
        id AS email_template_history_id,  -- Uses same value as email_template_id
        id AS email_template_id,
        ...
    FROM email_template_history
)
```

### Correct SQL Logic
```sql
-- GT expects a unique hash/UUID identifier for each template version
-- The email_template_history_id should be a distinct identifier, not the same as email_template_id
SELECT
    history_id AS email_template_history_id,  -- Should use a separate history ID field
    id AS email_template_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * A unique identifier for each version of an email template
  * This should be distinct from the email_template_id

* **What the SQL actually computes:**
  * Uses the same `id` field for both email_template_history_id and email_template_id
  * This results in identical values (e.g., 1055 for both)
  * GT expects a hash/UUID value (e.g., "1bce08e1b36ed0da2941560e9455649e")

---

## Evidence

**Sample mismatches:**

| EMAIL_TEMPLATE_ID | GT (hash) | Pred (integer) |
| ----------------- | --------- | -------------- |
| 1055 | 1bce08e1b36ed0da2941560e9455649e | 1055 |
| 1078 | 8bdc9a8733e204244abcf51351e8aaba | 1078 |
| 1080 | 02c71b2b28da9735b6b084863ab1ed32 | 1080 |
| 1098 | 4464ee6c7088d2a3a1f37b70f3fb6cf1 | 1098 |
| 1116 | b284590e45ddadac3100d058d390e095 | 1116 |

**Impact:**
* Current implementation: **0/79 matches (0%)**
* The GT expects a separate hash/UUID identifier for the template history version

---

## Result

**Complete mismatch - ID source field is incorrect**

**Key insight:**
The email_template_history source table likely has a separate field for the history ID that is a hash/UUID. The SQL incorrectly uses the template `id` field for both email_template_id and email_template_history_id, when they should be different fields. The correct field for email_template_history_id would be a dedicated history identifier column in the source data.
