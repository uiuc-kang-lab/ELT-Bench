# Column Mismatch Summary: OLDEST_EVENT_ID

## Database: talkingdata
## Table: labels
## Column: OLDEST_EVENT_ID

### Description
The id of the oldest event belongs to the label category, with ties broken by the ascending order of the event id.

---

## Root Cause: Definition of "Oldest Event" is Unclear

The SQL uses `MIN(EVENT_ID)` to find the "oldest" event, interpreting "oldest" as the smallest event_id. However, the ground truth appears to use a different methodology that does not correspond to either:
1. Minimum event_id
2. Oldest timestamp with ties broken by event_id

### Incorrect SQL (Predicted)
```sql
oldest_events AS (
    SELECT
        al.LABEL_ID,
        MIN(ae.EVENT_ID) AS oldest_event_id
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    INNER JOIN {{ source('airbyte_schema', 'APP_EVENTS') }} ae
        ON al.APP_ID = ae.APP_ID
    WHERE al.LABEL_ID IS NOT NULL
    GROUP BY al.LABEL_ID
)
```

### Expected SQL (Based on Description)
```sql
-- If "oldest" means by timestamp, ties broken by event_id:
oldest_events AS (
    SELECT
        al.LABEL_ID,
        FIRST_VALUE(ae.EVENT_ID) OVER (
            PARTITION BY al.LABEL_ID
            ORDER BY e.TIMESTAMP ASC, ae.EVENT_ID ASC
        ) AS oldest_event_id
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    INNER JOIN {{ source('airbyte_schema', 'APP_EVENTS') }} ae ON al.APP_ID = ae.APP_ID
    INNER JOIN {{ source('airbyte_schema', 'EVENTS') }} e ON ae.EVENT_ID = e.EVENT_ID
)
```

---

## Why the Original Logic Is Wrong

1. **Semantic Ambiguity:**
   - "Oldest event" could mean: (a) smallest event_id, or (b) earliest timestamp
   - The SQL assumes smallest event_id
   - Neither interpretation matches the ground truth values

2. **Investigation Results:**
   - For Label 10: Min event_id = 29, Oldest by timestamp = 1491116, GT = 3967
   - Event 29 timestamp: 2016-05-01 00:31:40.0
   - Event 3967 timestamp: 2016-05-03 06:07:53.0 (LATER, not oldest)
   - Event 1491116 timestamp: 2016-04-30 23:54:25.0 (OLDEST by time)

3. **Ground Truth Methodology Unknown:**
   - GT values do not correspond to MIN(event_id)
   - GT values do not correspond to oldest timestamp
   - The specific filtering or calculation method used by GT is unclear

---

## Evidence

### Sample Labels Showing Discrepancy

| Label ID | Min Event ID | Oldest by Time | GT Value | Match? |
|----------|-------------|----------------|----------|--------|
| 10 | 29 | 1491116 | 3967 | No |
| 100 | 40 | 186148 | 30157 | No |
| 1003 | 2 | 291991 | 11542 | No |
| 1005 | 7 | 1077000 | 129409 | No |
| 101 | 104 | 1045855 | 79641 | No |

### Timestamp Analysis for Label 10

```
Event 29:      2016-05-01 00:31:40.0 (Predicted - MIN event_id)
Event 1491116: 2016-04-30 23:54:25.0 (Oldest by timestamp)
Event 3967:    2016-05-03 06:07:53.0 (Ground Truth - NOT oldest)
```

### Statistical Summary

```
Total labels: 930
Labels with differences: 469 (50.4%)
Labels where GT is NULL but Predicted has value: Present
Labels where both have values but differ: Present
```

---

## Impact

| Metric | Value |
|--------|-------|
| Total Labels | 930 |
| Mismatched Labels | 469 |
| Match Rate | 49.6% |
| Root Cause | Unknown GT methodology |

---

## Result

**Status:** MISMATCH - Requires Clarification

The column fails validation due to:
1. Ambiguous definition of "oldest event"
2. Ground truth methodology does not match MIN(event_id)
3. Ground truth methodology does not match oldest timestamp

**Investigation Notes:**
- The SQL correctly implements MIN(EVENT_ID) as one interpretation of "oldest"
- The column description suggests timestamp-based ordering with event_id as tiebreaker
- Neither interpretation matches the ground truth

**Potential Explanations:**
1. Ground truth may use a different source table (e.g., EVENTS_RELEVANT)
2. Ground truth may apply additional filtering (e.g., specific user subset, active status)
3. Ground truth may use a different joining methodology

**Recommendation:**
Review the ground truth generation logic to understand the exact definition of "oldest event" being used.
