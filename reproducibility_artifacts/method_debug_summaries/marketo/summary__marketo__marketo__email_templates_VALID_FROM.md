# Column Mismatch Summary

## Database: marketo
## Table: marketo__email_templates
## Column: VALID_FROM

**Description:**
When the version of the email template was is valid from.

---

## Root Cause
**Wrong column used: SQL uses `created_at` as `valid_from` instead of `updated_at`**

### Incorrect SQL Logic
```sql
email_template_versions AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY email_template_id ORDER BY updated_timestamp) AS inferred_version,
        created_timestamp AS valid_from,  -- WRONG: uses created_at
        LEAD(created_timestamp) OVER (PARTITION BY email_template_id ORDER BY updated_timestamp) AS valid_to
    FROM email_template_history
)
```

### Correct SQL Logic
```sql
email_template_versions AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY email_template_id ORDER BY updated_timestamp) AS inferred_version,
        updated_timestamp AS valid_from,  -- CORRECT: uses updated_at
        LEAD(updated_timestamp) OVER (PARTITION BY email_template_id ORDER BY updated_timestamp) AS valid_to
    FROM email_template_history
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * `valid_from` indicates when this version of the template became valid
  * For SCD (Slowly Changing Dimension), each version's validity starts when it was updated

* **What the SQL actually computes:**
  * Uses `created_at` which is the same for all versions of a template
  * For template 1055 with 5 versions, all have `created_at = 2020-01-09 19:19:24.000`
  * But each version has a different `updated_at` timestamp

**Data example for template 1055:**
| Version | created_at | updated_at | GT VALID_FROM |
| ------- | ---------- | ---------- | ------------- |
| 1 | 2020-01-09 19:19:24.000 | 2020-02-05 19:50:09.000 | 2020-02-05 19:50:09.000 |
| 2 | 2020-01-09 19:19:24.000 | 2020-02-26 17:51:44.000 | 2020-02-26 17:51:44.000 |
| 3 | 2020-01-09 19:19:24.000 | 2020-03-13 18:10:24.000 | 2020-03-13 18:10:24.000 |
| 4 | 2020-01-09 19:19:24.000 | 2020-03-31 00:03:25.000 | 2020-03-31 00:03:25.000 |
| 5 (most recent) | 2020-01-09 19:19:24.000 | 2020-04-01 19:46:04.000 | 2020-04-01 19:46:04.000 |

---

## Evidence

**Key comparison demonstrating the error:**

| EMAIL_TEMPLATE_ID | GT VALID_FROM | Predicted VALID_FROM |
| ----------------- | ------------- | -------------------- |
| 1055 | 2020-04-01 19:46:04.000 | 2020-01-09 19:19:24.000 |
| 1158 | 2020-02-25 23:49:22.000 | 2020-02-05 18:27:51.000 |
| 1245 | 2020-02-21 16:39:28.000 | 2020-02-13 21:18:00.000 |
| 1272 | 2020-02-18 19:22:28.000 | 2020-02-16 06:27:16.000 |

**Impact:**
* Current implementation: **65/79 matches (82.3%)**
* Corrected implementation: **79/79 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The fix requires changing `valid_from` from `created_timestamp` to `updated_timestamp` in the window function logic. This ensures each version's validity period starts from when it was updated, not when the original template was created.
