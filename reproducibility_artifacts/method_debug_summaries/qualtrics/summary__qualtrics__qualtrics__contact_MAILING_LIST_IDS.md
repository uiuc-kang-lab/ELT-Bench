# Column Mismatch Summary

## Database: qualtrics
## Table: qualtrics__contact
## Column: MAILING_LIST_IDS

### Description
Comma-separated list of mailing list IDs the record is associated with.

---

## Root Cause
**Core contacts have mailing_list_id in source table, not in contact_mailing_list_membership**

The SQL only looks up mailing lists from `contact_mailing_list_membership` table, which only contains directory contacts (CID_*). Core contacts have their mailing list stored directly in the `core_contact.mailing_list_id` column.

### Incorrect SQL Logic
```sql
mailing_list_info AS (
    SELECT
        contact_id,
        LISTAGG(mailing_list_id, ',') WITHIN GROUP (ORDER BY mailing_list_id) AS mailing_list_ids,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.contact_mailing_list_membership
    GROUP BY contact_id
)
-- This only finds directory contacts (CID_*), not core contacts (hersanid)
```

### Correct SQL Logic
```sql
-- For core contacts, get mailing_list_id directly from core_contact table
core_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        ...
        CAST(mailing_list_id AS VARCHAR) AS mailing_list_ids,  -- Direct from core_contact
        CASE WHEN mailing_list_id IS NOT NULL AND unsubscribed = FALSE THEN 1 ELSE 0 END AS count_mailing_lists_subscribed_to,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.core_contact
),

-- For directory contacts, aggregate from contact_mailing_list_membership
directory_mailing_list_info AS (
    SELECT
        contact_id,
        LISTAGG(mailing_list_id, ',') WITHIN GROUP (ORDER BY mailing_list_id) AS mailing_list_ids,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.contact_mailing_list_membership
    GROUP BY contact_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: All mailing list IDs associated with a contact, from any source
* **What the SQL actually computes**: Only mailing lists from `contact_mailing_list_membership` table

**Schema semantics from `source_schemas`:**
- `contact_mailing_list_membership`: Contains mailing list memberships for **directory contacts** only (contact_id starts with CID_)
- `core_contact.mailing_list_id`: Contains the mailing list ID for **core contacts** directly in the record

---

## Evidence

**Key comparison demonstrating the error:**

| Contact ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| hersanid | NULL | ML_553543t34t534 | ML_553543t34t534 |

**Source data for contact "hersanid" (core_contact):**
- `core_contact.mailing_list_id` = 'ML_553543t34t534'
- Contact NOT in `contact_mailing_list_membership` table

**Impact:**
* Current implementation: **0/1 matches (0%)**
* Corrected implementation: **1/1 matches (100%)**

---

## Result
**Correction needed for core contacts**

For core contacts, the mailing_list_id must be retrieved directly from the `core_contact` table, not from `contact_mailing_list_membership`.

**Contact with mailing list:**
* hersanid: ML_553543t34t534
