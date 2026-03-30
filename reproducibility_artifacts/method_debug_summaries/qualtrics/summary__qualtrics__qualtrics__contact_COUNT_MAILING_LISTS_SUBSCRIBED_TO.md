# Column Mismatch Summary

## Database: qualtrics
## Table: qualtrics__contact
## Column: COUNT_MAILING_LISTS_SUBSCRIBED_TO

### Description
Count of distinct mailing lists the contact is a member of and has not opted out of.

---

## Root Cause
**Core contacts have mailing list subscription status in source table, not in contact_mailing_list_membership**

The SQL only counts mailing lists from `contact_mailing_list_membership` table, which only contains directory contacts. Core contacts have their mailing list and subscription status directly in the `core_contact` table.

### Incorrect SQL Logic
```sql
mailing_list_info AS (
    SELECT
        contact_id,
        SUM(CASE WHEN unsubscribed = FALSE THEN 1 ELSE 0 END) AS count_mailing_lists_subscribed_to,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.contact_mailing_list_membership
    GROUP BY contact_id
)
-- Core contacts (like "hersanid") not found here -> COALESCE returns 0
```

### Correct SQL Logic
```sql
-- For core contacts, check if they have a mailing_list_id and are not unsubscribed
core_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        ...
        CASE
            WHEN mailing_list_id IS NOT NULL AND unsubscribed = FALSE THEN 1
            ELSE 0
        END AS count_mailing_lists_subscribed_to,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.core_contact
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count of mailing lists the contact is subscribed to
* **What the SQL actually computes**: Count only from `contact_mailing_list_membership` (directory contacts only)

**Schema semantics from `source_schemas`:**
- `core_contact.mailing_list_id`: The mailing list the core contact belongs to
- `core_contact.unsubscribed`: Boolean indicating if the user unsubscribed

For core contact "hersanid":
- `mailing_list_id` = 'ML_553543t34t534' (has mailing list)
- `unsubscribed` = FALSE (not opted out)
- Therefore: COUNT_MAILING_LISTS_SUBSCRIBED_TO = 1

---

## Evidence

**Key comparison demonstrating the error:**

| Contact ID | Wrong Logic | Correct Logic | Ground Truth |
| ---------- | ----------- | ------------- | ------------ |
| hersanid | 0 | 1 | 1 |

**Source data for contact "hersanid":**
- `core_contact.mailing_list_id` = 'ML_553543t34t534'
- `core_contact.unsubscribed` = FALSE
- Expected count: 1

**Impact:**
* Current implementation: **0/1 matches (0%)**
* Corrected implementation: **1/1 matches (100%)**

---

## Result
**Correction needed for core contacts**

For core contacts, the subscription count must be computed from `core_contact.mailing_list_id` and `core_contact.unsubscribed` columns, not from `contact_mailing_list_membership`.

**Contacts with subscriptions:**
* hersanid: subscribed to 1 mailing list (ML_553543t34t534)
