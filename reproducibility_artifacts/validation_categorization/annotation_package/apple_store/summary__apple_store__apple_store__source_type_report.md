# Column Mismatch Summary

## Database: apple_store
## Table: apple_store__source_type_report
## Columns: DATE_DAY, APP_ID, APP_NAME, SOURCE_TYPE, IMPRESSIONS, PAGE_VIEWS, FIRST_TIME_DOWNLOADS, REDOWNLOADS, TOTAL_DOWNLOADS, ACTIVE_DEVICES, DELETIONS, INSTALLATIONS, SESSIONS

### Description
Each record represents daily metrics by app_id and source_type. Source types include App Store Browse, App Store Search, App Referrers, Web Referrers, App Clips, Unavailable, Institutional Purchases, and Null.

---

## Root Cause
**Granularity mismatch: Predicted SQL generates all possible date/app_id/source_type combinations via FULL OUTER JOINs, while GT only includes specific filtered combinations**

### Incorrect SQL Logic
```sql
SELECT
    COALESCE(asd.date_day, dd.date_day, ud.date_day) AS date_day,
    COALESCE(asd.app_id, dd.app_id, ud.app_id) AS app_id,
    COALESCE(asd.source_type, dd.source_type, ud.source_type, 'Null') AS source_type,
    ...
FROM app_store_device asd
FULL OUTER JOIN downloads_device dd ON ...
FULL OUTER JOIN usage_device ud ON ...
```

### Correct SQL Logic
```sql
-- The FULL OUTER JOINs create extra rows when data doesn't align perfectly
-- across source tables. GT appears to require data from specific source
-- combinations or applies additional filtering.

-- Option 1: Use INNER JOINs instead of FULL OUTER JOINs
-- Option 2: Apply filtering to only include rows where primary metrics exist
-- Option 3: Filter to specific date ranges present in all source tables
```

---

## Why the Original Logic Is Wrong

* **What GT expects**: Only include rows where there's meaningful data for the specific date/app_id/source_type combination. The ground truth has 9 rows with specific dates and source types.

* **What the SQL computes**: Uses FULL OUTER JOINs which generate all possible combinations where data exists in ANY source table, resulting in 29 rows. This includes dates/source_types that only appear in one source table.

* **Row filtering difference**:
  - GT dates: 2020-11-15, 2021-02-24, 2021-03-17, 2021-06-06, 2021-06-24, 2021-07-12, 2021-08-23, 2021-10-03, 2021-10-06
  - GT source types: App Store Browse, App Store Search, Institutional Purchase, Unavailable
  - Predicted includes additional dates (2020-11-27, 2020-12-22, etc.) and source types (App Referrer, Web Referrer)

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total rows | 9 | 29 |
| Matching rows | 9 | 9 |
| Extra rows in Pred | 0 | 20 |

**For the 9 matching rows, ALL column values match perfectly:**

| Column | Match Rate |
| ------ | ---------- |
| APP_NAME | 9/9 (100%) |
| IMPRESSIONS | 9/9 (100%) |
| PAGE_VIEWS | 9/9 (100%) |
| FIRST_TIME_DOWNLOADS | 9/9 (100%) |
| REDOWNLOADS | 9/9 (100%) |
| TOTAL_DOWNLOADS | 9/9 (100%) |
| ACTIVE_DEVICES | 9/9 (100%) |
| DELETIONS | 9/9 (100%) |
| INSTALLATIONS | 9/9 (100%) |
| SESSIONS | 9/9 (100%) |

**Example extra rows in Predicted:**
- 2020-11-27 / App Store Browse
- 2020-12-22 / Web Referrer
- 2021-01-04 / App Store Search
- 2021-01-09 / Web Referrer

**Impact:**
* Current implementation: **9/29 row matches (31.0%)** - 20 extra rows
* Corrected implementation would: **9/9 matches (100%)**

---

## Result
**Column values are correct, but row filtering is too permissive**

**Key insight:**
The FULL OUTER JOIN approach creates rows for any date/app_id/source_type combination that exists in ANY of the source tables (app_store_device, downloads_device, usage_device). The ground truth appears to only include rows where data meets certain criteria across sources. The fix would involve using INNER JOINs or applying additional WHERE clauses to filter out sparse data combinations.
