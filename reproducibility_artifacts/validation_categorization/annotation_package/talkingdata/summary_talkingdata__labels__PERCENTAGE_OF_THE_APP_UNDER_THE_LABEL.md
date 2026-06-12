# Column Mismatch Summary: PERCENTAGE_OF_THE_APP_UNDER_THE_LABEL

## Database: talkingdata
## Table: labels
## Column: PERCENTAGE_OF_THE_APP_UNDER_THE_LABEL

### Description
The percentage of the app that belongs to the label category.

---

## Root Cause: Wrong Denominator - DISTINCT vs Total Rows

The SQL calculates the percentage using `COUNT(DISTINCT APP_ID)` for both numerator and denominator, but the ground truth uses total row count in `app_labels` as the denominator.

### Incorrect SQL (Predicted)
```sql
total_apps AS (
    SELECT COUNT(DISTINCT APP_ID) AS total_app_count
    FROM {{ source('airbyte_schema', 'APP_LABELS') }}
),

app_percentages AS (
    SELECT
        al.LABEL_ID,
        COUNT(DISTINCT al.APP_ID) * 100.0 / ta.total_app_count AS percentage_of_the_app_under_the_label
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    CROSS JOIN total_apps ta
    WHERE al.LABEL_ID IS NOT NULL
    GROUP BY al.LABEL_ID, ta.total_app_count
)
```

### Correct SQL (Required)
```sql
total_apps AS (
    SELECT COUNT(*) AS total_app_count
    FROM {{ source('airbyte_schema', 'APP_LABELS') }}
),

app_percentages AS (
    SELECT
        al.LABEL_ID,
        COUNT(*) * 100.0 / ta.total_app_count AS percentage_of_the_app_under_the_label
    FROM {{ source('airbyte_schema', 'APP_LABELS') }} al
    CROSS JOIN total_apps ta
    WHERE al.LABEL_ID IS NOT NULL
    GROUP BY al.LABEL_ID, ta.total_app_count
)
```

---

## Why the Original Logic Is Wrong

1. **Denominator Mismatch:**
   - Predicted uses `COUNT(DISTINCT APP_ID)` = 113,211 unique apps
   - Ground truth uses `COUNT(*)` = 459,943 total rows
   - This results in percentages being approximately 4x higher in predicted

2. **Numerator Mismatch:**
   - Predicted counts distinct app_ids per label
   - Ground truth counts all rows per label (including duplicates)

3. **Ratio Analysis:**
   - Total rows / Distinct apps = 459,943 / 113,211 = 4.06
   - This explains why predicted percentages are ~4x higher than ground truth

---

## Evidence

### Calculation Comparison

| Label ID | Rows | Distinct | Pred % | GT % | Pred/GT Ratio |
|----------|------|----------|--------|------|---------------|
| 10 | 95 | 90 | 0.0804 | 0.0207 | 3.89 |
| 100 | 957 | 938 | 0.8441 | 0.2081 | 4.06 |
| 1000 | 3 | 3 | 0.0028 | 0.0007 | 4.26 |
| 1001 | 3 | 3 | 0.0028 | 0.0007 | 4.26 |

### Detailed Example: Label ID 10

```
app_labels table statistics:
- Total rows in table: 459,943
- Total distinct app_ids: 113,211

Label 10 statistics:
- Rows with label_id=10: 95
- Distinct app_ids with label_id=10: 90

Predicted calculation:
  90 / 113,211 * 100 = 0.0795% (but shows 0.0804 due to join logic)

Ground truth calculation:
  95 / 459,943 * 100 = 0.0207%
```

### Statistical Summary

```
Total labels: 930
Labels with differences: 507 (54.5%)

Average ratio (Predicted/GT): ~4.0
This matches the ratio of total rows to distinct apps
```

---

## Impact

| Metric | Value |
|--------|-------|
| Total Labels | 930 |
| Mismatched Labels | 507 |
| Match Rate | 45.5% |
| Root Cause | DISTINCT count vs row count |

---

## Result

**Status:** MISMATCH

The column fails validation due to:
1. Using `COUNT(DISTINCT APP_ID)` instead of `COUNT(*)` for both numerator and denominator
2. Resulting percentages are approximately 4x higher than ground truth

**Fix Required:**
1. Change denominator from `COUNT(DISTINCT APP_ID)` to `COUNT(*)` for total apps
2. Change numerator from `COUNT(DISTINCT APP_ID)` to `COUNT(*)` for label-specific count
3. This ensures percentages represent the proportion of all app-label associations
