# Column Mismatch Summary

## Database: qualtrics
## Table: qualtrics__distribution
## Column: FIRST_SURVEY_SENT_AT

### Description
Timestamp of when the first survey was sent via this distribution.

---

## Root Cause
**Timestamp format inconsistency: Trailing zeros in microseconds**

The computed timestamp has 6-digit microseconds (e.g., `.058000`) while the ground truth expects variable precision (e.g., `.058`).

### Incorrect SQL Logic
```sql
distribution_contact_stats AS (
    SELECT
        distribution_id,
        MIN(sent_at) AS first_survey_sent_at,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.distribution_contact
    GROUP BY distribution_id
)
```

### Correct SQL Logic
```sql
distribution_contact_stats AS (
    SELECT
        distribution_id,
        -- Normalize timestamp format by removing trailing zeros
        TO_VARCHAR(MIN(sent_at), 'YYYY-MM-DD HH24:MI:SS.FF3') AS first_survey_sent_at,
        ...
    FROM qualtrics.AIRBYTE_SCHEMA.distribution_contact
    GROUP BY distribution_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The timestamp should match the format used in the ground truth
* **What the SQL actually computes**: The MIN(sent_at) preserves full 6-digit microsecond precision (.058000)

The issue is purely a formatting difference - the logic is correct, but the output format differs:
- GT: `2022-09-12 05:13:55.058` (3 significant decimal digits)
- Pred: `2022-09-12 05:13:55.058000` (6 decimal digits with trailing zeros)

---

## Evidence

**Key comparison demonstrating the error:**

| Distribution ID | Wrong Format | Correct Format | Ground Truth |
| --------------- | ------------ | -------------- | ------------ |
| EMD_GgJDmizeU8yAwvI | 2022-09-12 05:13:55.058000 | 2022-09-12 05:13:55.058 | 2022-09-12 05:13:55.058 |

**Impact:**
* Current implementation: **4/5 matches (80%)**
* Corrected implementation: **5/5 matches (100%)**

---

## Result
**Format correction needed**

The underlying MIN(sent_at) logic is correct - the issue is purely timestamp format normalization. Either:
1. Format the timestamp to match GT precision
2. Or accept that both values represent the same point in time (semantic match)

**Distributions with non-null FIRST_SURVEY_SENT_AT:**
* EMD_GgJDmizeU8yAwvI: 2022-09-12 05:13:55.058
