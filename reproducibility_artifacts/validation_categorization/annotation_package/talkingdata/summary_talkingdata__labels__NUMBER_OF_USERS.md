# Column Mismatch Summary: NUMBER_OF_USERS

## Database: talkingdata
## Table: labels
## Column: NUMBER_OF_USERS

### Description
The number of users belong to the label category, replace NULL values with 0.

---

## Root Cause: COUNT DISTINCT vs COUNT (rows)

The SQL uses `COUNT(DISTINCT APP_ID)` to count unique apps, but the ground truth counts total rows in `app_labels` for each label (which includes duplicate app_id entries).

### Incorrect SQL (Predicted)
```sql
user_counts AS (
    SELECT
        LABEL_ID,
        COUNT(DISTINCT APP_ID) AS number_of_users
    FROM {{ source('airbyte_schema', 'APP_LABELS') }}
    WHERE LABEL_ID IS NOT NULL
    GROUP BY LABEL_ID
)
```

### Correct SQL (Required)
```sql
user_counts AS (
    SELECT
        LABEL_ID,
        COUNT(APP_ID) AS number_of_users
    FROM {{ source('airbyte_schema', 'APP_LABELS') }}
    WHERE LABEL_ID IS NOT NULL
    GROUP BY LABEL_ID
)
```

---

## Why the Original Logic Is Wrong

1. **Data Structure Misunderstanding:**
   - The `app_labels` table contains duplicate entries (same app_id can appear multiple times for the same label_id)
   - Ground truth counts ALL rows, including duplicates
   - Predicted counts only DISTINCT app_ids

2. **Terminology Confusion:**
   - "Users" in the description likely refers to app-label associations (rows), not unique apps
   - Each row in `app_labels` represents a user-label relationship

3. **Impact:**
   - For labels with duplicate app_id entries, predicted < ground truth
   - For labels without duplicates, values may still differ due to join logic

---

## Evidence

### Sample Labels Showing Discrepancy

| Label ID | Total Rows | Distinct Apps | Predicted | Ground Truth |
|----------|-----------|---------------|-----------|--------------|
| 10 | 95 | 90 | 87 | 95 |
| 100 | 957 | 938 | 913 | 957 |
| 1005 | 228 | 228 | 225 | 228 |

### Example: Label ID 10
```
app_labels table for label_id = 10:
- Total rows: 95
- Distinct app_ids: 90
- Duplicate app_ids found: 5 entries are duplicates

Sample duplicate entries:
app_id                       label_id
-2069350067877045707         10       (appears 2x)
-1871970125134889473         10       (appears 2x)
3236904982787270514          10       (appears 2x)
8303019475066309465          10       (appears 2x)
673195149533538598           10       (appears 2x)
```

### Statistical Summary

```
Total labels: 930
Labels with differences: 241 (25.9%)

Key observations:
- Predicted values are consistently <= Ground Truth values
- Difference is due to duplicate app_id entries per label
```

---

## Impact

| Metric | Value |
|--------|-------|
| Total Labels | 930 |
| Mismatched Labels | 241 |
| Match Rate | 74.1% |
| Root Cause | COUNT DISTINCT vs COUNT |

---

## Result

**Status:** MISMATCH

The column fails validation due to:
1. Using `COUNT(DISTINCT APP_ID)` instead of `COUNT(APP_ID)`
2. Not counting duplicate app-label associations

**Fix Required:**
1. Change `COUNT(DISTINCT APP_ID)` to `COUNT(APP_ID)` or `COUNT(*)`
2. This will count all rows (user-label associations) including duplicates
