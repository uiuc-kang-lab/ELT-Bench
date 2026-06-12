# Column Mismatch Summary

## Database: qualtrics
## Table: qualtrics__contact
## Column: IS_RESEARCH_CORE_CONTACT

### Description
Boolean representing whether the contact came from the (to-be-deprecated) Research Core API endpoint (ie stored in the core_contact table).

---

## Root Cause
**No error found - Current implementation is CORRECT**

The current SQL implementation correctly sets this boolean flag based on the source table.

### Current SQL Logic (Correct)
```sql
directory_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        TRUE AS is_xm_directory_contact,
        FALSE AS is_research_core_contact,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.directory_contact
),

core_contacts AS (
    SELECT
        CAST(id AS VARCHAR) AS contact_id,
        FALSE AS is_xm_directory_contact,
        TRUE AS is_research_core_contact,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.core_contact
)
```

---

## Why the Implementation Is Correct

The current implementation correctly:
1. **Sets FALSE for directory contacts**: Records from `directory_contact` table get `is_research_core_contact = FALSE`
2. **Sets TRUE for core contacts**: Records from `core_contact` table get `is_research_core_contact = TRUE`

---

## Evidence

**Verification results:**

| Metric | Value |
| ------ | ----- |
| Comparable contacts | 1 |
| Matches | 1 |
| Match rate | 100.0% |

For contact "hersanid" (core contact):
- GT: IS_RESEARCH_CORE_CONTACT = True
- Pred: IS_RESEARCH_CORE_CONTACT = True

**Impact:**
* Current implementation: **1/1 matches (100%)**

---

## Result
**Perfect match - No correction needed**

The SQL implementation correctly identifies core contacts vs directory contacts.
