# Column Mismatch Summary

## Database: amplitude
## Table: amplitude__event_enhanced
## Column: VALUE

### Description
Name of the event in the raw data.

---

## Root Cause
**Hardcoded NULL instead of joining with event_type table to get the `value` column**

### Incorrect SQL Logic
```sql
event_type_data as (
    select
        id as event_type_id,
        name as event_type_name,
        totals,
        value
    from {{ source('airbyte', 'event_type') }}
),
...
final as (
    select
        ...
        null as totals,  -- from event_type table
        null as value,   -- from event_type table  <-- WRONG: should use et.value
        ...
    from event_numbered e
    left join session_metrics sm
        on e.unique_session_id = sm.unique_session_id
    left join user_session_numbered usn
        on e.unique_session_id = usn.unique_session_id
)
```

### Correct SQL Logic
```sql
event_type_data as (
    select
        id as event_type_id,
        name as event_type_name,
        totals,
        value
    from {{ source('airbyte', 'event_type') }}
),

event_with_type as (
    select
        e.*,
        {{ dbt_utils.generate_surrogate_key(['et.event_type_id']) }} as unique_event_type_id,
        et.event_type_name,
        et.value  -- Include value from event_type
    from event_data e
    left join event_type_data et
        on e.event_type_id = et.event_type_id
),
...
final as (
    select
        ...
        e.value,  -- Use the joined value
        ...
    from event_numbered e
    ...
)
```

---

## Why the Original Logic Is Wrong

* **Hardcoded NULL:** Despite correctly defining `value` in the `event_type_data` CTE and joining with event_type, the final SELECT hardcodes `null as value`.

* **Join exists but unused:** The SQL already joins event_data with event_type_data on event_type_id, but the `value` column from event_type is never carried through to the final output.

* **Column available in CTE:** The `event_type_data` CTE includes `value`, but it's not selected in `event_with_type` and the final output uses `null as value` instead.

**What the column description means:**
- The `value` column from the `event_type` table represents the raw event name
- Should be populated when event has a valid event_type_id that matches event_type table

**What the SQL actually computes:**
- Always returns NULL regardless of whether a match exists in event_type

---

## Evidence

**Key comparison demonstrating the error:**

| EVENT_ID | EVENT_TYPE | EVENT_TYPE_ID | GT VALUE | Pred VALUE |
| -------- | ---------- | ------------- | -------- | ---------- |
| 242501284 | watch_test_amplitude | 10839772.0 | watch_test_amplitude | NULL |
| 260278357 | watch_test_amplitude_3 | 10840181.0 | watch_test_amplitude_3 | NULL |
| 370485021 | watch_test_amplitude | 10839772.0 | watch_test_amplitude | NULL |
| 913233589 | test_event_01 | 10862478.0 | test_event_01 | NULL |
| 47590376 | watch_test_amplitude_2 | NULL | NULL | NULL |
| 86821571 | aaa... | NULL | NULL | NULL |

**event_type table data:**
| id | name | value |
| -- | ---- | ----- |
| 10862478 | test_event_01 | test_event_01 |
| 10840181 | watch_test_amplitude_3 | watch_test_amplitude_3 |
| 10839772 | watch_test_amplitude | watch_test_amplitude |

**Impact:**
* Current implementation: **6/10 matches (60%)** - only NULL values match
* Corrected implementation: **10/10 matches (100%)**

---

## Result
**Column defined but not propagated to final output**

The fix requires:
1. Include `et.value` in the `event_with_type` CTE when joining with event_type_data
2. Propagate `value` through subsequent CTEs
3. Select `e.value` in the final output instead of `null as value`

**Events that should have non-NULL VALUE:**
* 242501284: watch_test_amplitude
* 260278357: watch_test_amplitude_3
* 370485021: watch_test_amplitude
* 913233589: test_event_01
