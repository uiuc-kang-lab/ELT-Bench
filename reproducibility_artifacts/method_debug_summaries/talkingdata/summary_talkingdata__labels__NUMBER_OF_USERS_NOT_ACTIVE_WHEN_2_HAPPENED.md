# Column Mismatch Summary: NUMBER_OF_USERS_NOT_ACTIVE_WHEN_2_HAPPENED

## Database: talkingdata
## Table: labels
## Column: NUMBER_OF_USERS_NOT_ACTIVE_WHEN_2_HAPPENED

### Description
The number of users belong to the label category who were not active when event no.2 happened, replace NULL values with 0.

---

## Root Cause: Different Interpretation of "Not Active When Event 2 Happened"

The SQL interprets "not active when event 2 happened" as apps that were NOT in the active set for event 2 (including apps not present in event 2 at all). The ground truth interprets it as apps that WERE PRESENT in event 2 but had `is_active = 0`.

### Incorrect SQL (Predicted)
```sql
users_not_active_event_2 AS (
    SELECT
        al.LABEL_ID,
        COUNT(DISTINCT al.APP_ID) AS number_of_users_not_active_when_2_happened
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    LEFT JOIN (
        SELECT DISTINCT APP_ID
        FROM {{ source('airbyte_schema', 'APP_EVENTS') }}
        WHERE EVENT_ID = 2 AND IS_ACTIVE = 1
    ) ae2
        ON al.APP_ID = ae2.APP_ID
    WHERE al.LABEL_ID IS NOT NULL
        AND ae2.APP_ID IS NULL  -- Apps NOT in active set for event 2
    GROUP BY al.LABEL_ID
)
```

### Correct SQL (Required)
```sql
users_not_active_event_2 AS (
    SELECT
        al.LABEL_ID,
        COUNT(DISTINCT al.APP_ID) AS number_of_users_not_active_when_2_happened
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    INNER JOIN {{ source('airbyte_schema', 'APP_EVENTS') }} ae
        ON al.APP_ID = ae.APP_ID
    WHERE al.LABEL_ID IS NOT NULL
        AND ae.EVENT_ID = 2
        AND ae.IS_ACTIVE = 0  -- Apps present in event 2 but NOT active
    GROUP BY al.LABEL_ID
)
```

---

## Why the Original Logic Is Wrong

1. **Semantic Misinterpretation:**
   - **Predicted interpretation:** Count apps that were NOT active when event 2 happened = apps NOT in the active set (includes apps absent from event 2)
   - **Ground truth interpretation:** Count apps that WERE PRESENT in event 2 but were NOT active (is_active = 0)

2. **Key Difference:**
   - Event 2 has only 19 apps total, with 6 active and 13 not active
   - Predicted counts all label apps NOT in the 6 active apps (which is nearly all apps)
   - Ground truth counts only label apps among the 13 that were present but not active

3. **Impact:**
   - Predicted values are much larger (e.g., 87 for label 10)
   - Ground truth values are mostly 0 or very small (e.g., 0 for label 10)
   - Only labels with apps that overlap with the 13 inactive apps in event 2 have non-zero GT values

---

## Evidence

### Event 2 Statistics

```
Event 2 app_events:
- Total apps present: 19
- Active apps (is_active=1): 6
- Inactive apps (is_active=0): 13
```

### Sample Label Analysis

| Label ID | Total Apps | Predicted | GT | Apps in Event 2 (inactive) |
|----------|-----------|-----------|-----|---------------------------|
| 10 | 90 | 87 | 0 | 0 |
| 100 | 938 | 913 | 0 | 0 |
| 1003 | 44 | 44 | 1 | 1 |
| 548 | 9393 | 9289 | 16 | ~16 |

### Detailed Example: Label 1003

```
Label 1003:
- Total unique apps: 44
- Apps in event 2 but NOT active: 1 (matches GT)
- Apps not in event 2 at all: 43

Predicted: 44 (all apps not in the active set)
Ground Truth: 1 (only app present in event 2 with is_active=0)
```

### Value Distribution

```
Ground Truth distribution:
- Value 0: 882 labels (94.8%)
- Value 1-16: 48 labels (5.2%)

Predicted distribution:
- Varied values from 0 to thousands
- Much higher average than GT
```

---

## Impact

| Metric | Value |
|--------|-------|
| Total Labels | 930 |
| Mismatched Labels | 507 |
| Match Rate | 45.5% |
| Root Cause | LEFT JOIN vs INNER JOIN interpretation |

---

## Result

**Status:** MISMATCH

The column fails validation due to:
1. Using LEFT JOIN to find apps NOT in active set (includes apps absent from event 2)
2. Ground truth uses INNER JOIN to find apps PRESENT in event 2 with is_active=0

**Fix Required:**
1. Change from LEFT JOIN (exclude active) to INNER JOIN (only event 2 participants)
2. Filter for `EVENT_ID = 2 AND IS_ACTIVE = 0`
3. Count only apps that were present in event 2 but marked as not active

**Semantic Clarification:**
The phrase "not active when event 2 happened" means apps that participated in event 2 with `is_active = 0`, NOT all apps that were inactive during event 2 (which would include apps not participating in event 2 at all).
