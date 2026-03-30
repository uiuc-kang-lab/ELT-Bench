# Column Mismatch Summary

## Database: amplitude
## Table: amplitude__event_enhanced
## Column: SESSION_LENGTH_IN_MINUTES

### Description
The length of the session, in minutes

---

## Root Cause
**Data type difference: GT uses FLOAT (0.0, 11520.0) while predicted uses INTEGER (0, 11520)**

### Incorrect SQL Logic
```sql
session_metrics as (
    select
        unique_session_id,
        count(*) as events_per_session,
        min(event_time) as session_started_at,
        max(event_time) as session_ended_at,
        date(min(event_time)) as session_started_at_day,
        date(max(event_time)) as session_ended_at_day,
        datediff(minute, min(event_time), max(event_time)) as session_length_in_minutes
    from event_numbered
    group by unique_session_id
)
```

### Correct SQL Logic
```sql
session_metrics as (
    select
        unique_session_id,
        count(*) as events_per_session,
        min(event_time) as session_started_at,
        max(event_time) as session_ended_at,
        date(min(event_time)) as session_started_at_day,
        date(max(event_time)) as session_ended_at_day,
        CAST(datediff(minute, min(event_time), max(event_time)) AS FLOAT) as session_length_in_minutes
    from event_numbered
    group by unique_session_id
)
```

---

## Why the Original Logic Is Wrong

* **Data type mismatch:** The `datediff(minute, ...)` function returns an INTEGER, but the ground truth expects FLOAT values.

* **Semantic equivalence:** The actual numerical values are correct (0 vs 0.0, 11520 vs 11520.0), but the data type representation differs.

* **Schema expectation:** The ground truth schema appears to use FLOAT/DECIMAL for this column, storing values like `0.0` and `11520.0`.

**What the column description means:**
- The duration of the session in minutes (as a numeric value)

**What the SQL actually computes:**
- Correct duration calculation using datediff(minute, start, end)
- Returns INTEGER type instead of FLOAT

---

## Evidence

**Key comparison demonstrating the error:**

| EVENT_ID | SESSION_ID | GT SESSION_LENGTH_IN_MINUTES | Pred SESSION_LENGTH_IN_MINUTES | Values Match? |
| -------- | ---------- | ---------------------------- | ------------------------------ | ------------- |
| 47590376 | -1 | 0.0 | 0 | Numerically yes, type no |
| 86821571 | -1 | 11520.0 | 11520 | Numerically yes, type no |
| 242501284 | -1 | 0.0 | 0 | Numerically yes, type no |
| 260278357 | -1 | 0.0 | 0 | Numerically yes, type no |
| 913233589 | -1 | 11520.0 | 11520 | Numerically yes, type no |
| 959963246 | -1 | 11520.0 | 11520 | Numerically yes, type no |

**Note:** All values are numerically equivalent. The mismatch is purely a data type/representation issue.

**Impact:**
* Current implementation: **0/10 matches (0%)** - due to type comparison
* Corrected implementation (with CAST to FLOAT): **10/10 matches (100%)**

---

## Result
**Data type representation difference (INTEGER vs FLOAT)**

This is a minor data type issue, not a logic error. The calculation is correct, but the output type differs from the ground truth expectation.

**Fix options:**
1. `CAST(datediff(...) AS FLOAT)` - explicitly cast to float
2. `datediff(...) * 1.0` - multiply by float to convert
3. Accept as equivalent if the comparison system handles numeric equivalence

**Semantic accuracy:** The computed values are correct. This is a formatting/type compatibility issue rather than a semantic error.
