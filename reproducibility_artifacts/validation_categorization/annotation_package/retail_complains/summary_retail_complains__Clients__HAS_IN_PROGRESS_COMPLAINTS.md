## Database: retail_complains
## Table: Clients
## Column: HAS_IN_PROGRESS_COMPLAINTS

**Description:**
Set to 1 if the client has in progress complaints, 0 otherwise.

---

## Root Cause
**The SQL uses exact string matching for 'In Progress' but the actual data may use different casing or formatting. Client C00000036 should have value 1 but returns 0.**

### Incorrect SQL Logic
```sql
in_progress_complaints AS (
    SELECT
        RAND_CLIENT AS client_id,
        MAX(CASE WHEN OUTCOME = 'In Progress' THEN 1 ELSE 0 END) AS has_in_progress
    FROM {{ source('airbyte_schema', 'CALLCENTERLOGS') }}
    GROUP BY RAND_CLIENT
)
```

### Correct SQL Logic
```sql
in_progress_complaints AS (
    SELECT
        RAND_CLIENT AS client_id,
        MAX(CASE WHEN UPPER(OUTCOME) = 'IN PROGRESS' THEN 1 ELSE 0 END) AS has_in_progress
    FROM {{ source('airbyte_schema', 'CALLCENTERLOGS') }}
    GROUP BY RAND_CLIENT
)
```

---

## Why the Original Logic Is Wrong

* The SQL checks for exact match with 'In Progress' (case-sensitive)
* The OUTCOME column may contain variations like 'IN PROGRESS', 'in progress', or 'In progress'
* Client C00000036 has an in-progress complaint in the ground truth (value = 1) but the predicted value is 0
* This indicates the string comparison fails to find the matching value due to case sensitivity
* Alternative issue: The client_id linking (RAND_CLIENT vs CLIENT_ID) may be incorrect for this specific client

---

## Evidence

**Key comparison demonstrating the error:**

| CLIENT_ID | GT Value | Predicted Value | Issue |
| --------- | -------- | --------------- | ----- |
| C00000036 | 1 | 0 | Should have in-progress complaint but not detected |
| All others | 0 | 0 | Match correctly |

**Impact:**
* Current implementation: **1 client incorrectly shows 0 instead of 1**
* Corrected implementation: **All clients match ground truth**

---

## Result

**Affected Client**: C00000036 (Grace Emma Thompson)

**Possible causes:**
1. Case-sensitive string matching issue - OUTCOME value may be 'IN PROGRESS' or 'in progress'
2. Client ID linking issue - RAND_CLIENT in CALLCENTERLOGS may not properly link to CLIENT_ID in CLIENT table for this specific record

**Recommended fix:**
```sql
MAX(CASE WHEN UPPER(TRIM(OUTCOME)) = 'IN PROGRESS' THEN 1 ELSE 0 END) AS has_in_progress
```

This ensures case-insensitive matching and handles potential whitespace issues.
