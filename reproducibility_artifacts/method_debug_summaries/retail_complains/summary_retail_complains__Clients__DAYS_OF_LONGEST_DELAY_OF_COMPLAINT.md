## Database: retail_complains
## Table: Clients
## Column: DAYS_OF_LONGEST_DELAY_OF_COMPLAINT

**Description:**
The number of days of the longest delay in the client's complaint.

---

## Root Cause
**Minor data type precision mismatch - Ground truth returns decimal format (e.g., 4.0) while predicted returns integer format (e.g., 4).**

### Incorrect SQL Logic
```sql
longest_delay AS (
    SELECT
        e.CLIENT_ID,
        DATEDIFF(day, e.DATE_RECEIVED, e.DATE_SENT_TO_COMPANY) AS delay_days,
        ROW_NUMBER() OVER (PARTITION BY e.CLIENT_ID ORDER BY DATEDIFF(day, e.DATE_RECEIVED, e.DATE_SENT_TO_COMPANY) DESC) AS rn
    FROM {{ source('airbyte_schema', 'EVENTS') }} e
    WHERE e.DATE_SENT_TO_COMPANY IS NOT NULL AND e.DATE_RECEIVED IS NOT NULL
)
-- Returns integer: 4
```

### Correct SQL Logic
```sql
longest_delay AS (
    SELECT
        e.CLIENT_ID,
        CAST(DATEDIFF(day, e.DATE_RECEIVED, e.DATE_SENT_TO_COMPANY) AS FLOAT) AS delay_days,
        ROW_NUMBER() OVER (PARTITION BY e.CLIENT_ID ORDER BY DATEDIFF(day, e.DATE_RECEIVED, e.DATE_SENT_TO_COMPANY) DESC) AS rn
    FROM {{ source('airbyte_schema', 'EVENTS') }} e
    WHERE e.DATE_SENT_TO_COMPANY IS NOT NULL AND e.DATE_RECEIVED IS NOT NULL
)
-- Returns float: 4.0
```

---

## Why the Original Logic Is Wrong

* The core logic is correct - finding the maximum delay between DATE_RECEIVED and DATE_SENT_TO_COMPANY
* The mismatch is purely a data type precision issue
* Ground truth stores values as floats (4.0, 0.0, 1.0, 22.0)
* Predicted returns integers (4, 0, 1, 22)
* The actual values are equivalent, just different representations

---

## Evidence

**Key comparison demonstrating the error:**

| CLIENT_ID | GT Value | Predicted Value | Issue |
| --------- | -------- | --------------- | ----- |
| C00000001 | 4.0 | 4 | Float vs Integer format |
| C00000002 | 0.0 | 0 | Float vs Integer format |
| C00000003 | 1.0 | 1 | Float vs Integer format |
| C00000004 | 22.0 | 22 | Float vs Integer format |
| C00000019 | 175.0 | 175 | Float vs Integer format |

**Impact:**
* Current implementation: **Values match numerically but fail string comparison due to format**
* Corrected implementation: **Values match exactly with proper float casting**

---

## Result

**Status**: LIKELY MATCHED - The values are numerically identical, only differing in decimal representation.

**Fix**: Cast the DATEDIFF result to FLOAT to match ground truth format:
```sql
CAST(DATEDIFF(day, e.DATE_RECEIVED, e.DATE_SENT_TO_COMPANY) AS FLOAT) AS delay_days
```

This is a minor formatting issue rather than a logic error.
