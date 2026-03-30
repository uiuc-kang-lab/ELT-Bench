# Column Mismatch Summary

## Database: qualtrics
## Table: qualtrics__contact
## Column: CREATED_AT

### Description
The creation date and time of the record, expressed as an ISO 8601 value.

---

## Root Cause
**Core contacts have no creation_date column - must use _fivetran_synced**

The SQL sets CREATED_AT to NULL for core contacts, but the ground truth expects the `_fivetran_synced` timestamp as the creation date.

### Incorrect SQL Logic
```sql
core_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        ...
        CAST(NULL AS TIMESTAMP_NTZ) AS created_at  -- Incorrectly sets to NULL
    FROM qualtrics.AIRBYTE_SCHEMA.core_contact
    WHERE _fivetran_deleted = FALSE
)
```

### Correct SQL Logic
```sql
core_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        ...
        _fivetran_synced AS created_at  -- Use _fivetran_synced for core contacts
    FROM qualtrics.AIRBYTE_SCHEMA.core_contact
    WHERE _fivetran_deleted = FALSE
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The creation date and time of the record
* **What the SQL actually computes**: NULL for core contacts

**Schema semantics from `source_schemas`:**
- `directory_contact.creation_date`: The creation date and time of the record
- `core_contact`: No `creation_date` column exists; `_fivetran_synced` serves as the record creation timestamp

For core contact "hersanid":
- `_fivetran_synced` = '2023-06-05 03:06:31.097000'
- This is the appropriate creation timestamp for this record

---

## Evidence

**Key comparison demonstrating the error:**

| Contact ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| hersanid | NULL | 2023-06-05 03:06:31.097000 | 2023-06-05 03:06:31.097000 |

**Source data for contact "hersanid":**
- `core_contact._fivetran_synced` = '2023-06-05 03:06:31.097000'

**Impact:**
* Current implementation: **0/1 matches (0%)**
* Corrected implementation: **1/1 matches (100%)**

---

## Result
**Correction needed for core contacts**

For core contacts, use `_fivetran_synced` as the `created_at` timestamp instead of NULL, since `core_contact` table doesn't have a `creation_date` column.

**Core contacts with created_at:**
* hersanid: 2023-06-05 03:06:31.097000
