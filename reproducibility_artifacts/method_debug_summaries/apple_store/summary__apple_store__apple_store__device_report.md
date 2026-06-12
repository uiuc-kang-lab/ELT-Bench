# Column Mismatch Summary

## Database: apple_store
## Table: apple_store__device_report
## Columns: DATE_DAY, APP_ID, APP_NAME, SOURCE_TYPE, DEVICE, IMPRESSIONS, IMPRESSIONS_UNIQUE_DEVICE, PAGE_VIEWS, PAGE_VIEWS_UNIQUE_DEVICE, CRASHES, FIRST_TIME_DOWNLOADS, REDOWNLOADS, TOTAL_DOWNLOADS, ACTIVE_DEVICES, ACTIVE_DEVICES_LAST_30_DAYS, DELETIONS, INSTALLATIONS, SESSIONS

### Description
Each record represents daily subscription metrics by app_id, source_type and device.

---

## Root Cause
**Granularity mismatch: Predicted SQL generates double the rows via FULL OUTER JOINs across source tables**

### Incorrect SQL Logic
```sql
SELECT
    COALESCE(asd.date_day, dd.date_day, ud.date_day, ca.date_day) AS date_day,
    COALESCE(asd.app_id, dd.app_id, ud.app_id, ca.app_id) AS app_id,
    COALESCE(asd.source_type, dd.source_type, ud.source_type, 'Null') AS source_type,
    COALESCE(asd.device, dd.device, ud.device, ca.device) AS device,
    ...
FROM app_store_device asd
FULL OUTER JOIN downloads_device dd ON ...
FULL OUTER JOIN usage_device ud ON ...
FULL OUTER JOIN crashes_app_version ca ON ...
```

### Correct SQL Logic
```sql
-- Use INNER JOINs or apply filtering to match GT's row selection criteria
-- GT only includes rows where primary data exists across relevant sources
```

---

## Why the Original Logic Is Wrong

* **What GT expects**: 20 rows with specific date/app_id/source_type/device combinations.

* **What the SQL computes**: FULL OUTER JOINs across 4 source tables generate 40 rows (exactly double), including combinations where data exists in only one source table.

* **SOURCE_TYPE handling**: GT uses NaN for null sources, Predicted converts to string 'Null'.

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total rows | 20 | 40 |
| Matching rows | 20 | 20 |
| Extra rows in Pred | 0 | 20 |

**For the 20 matching rows, ALL column values match perfectly:**

| Column | Match Rate |
| ------ | ---------- |
| APP_NAME | 20/20 (100%) |
| IMPRESSIONS | 20/20 (100%) |
| IMPRESSIONS_UNIQUE_DEVICE | 20/20 (100%) |
| PAGE_VIEWS | 20/20 (100%) |
| PAGE_VIEWS_UNIQUE_DEVICE | 20/20 (100%) |
| CRASHES | 20/20 (100%) |
| FIRST_TIME_DOWNLOADS | 20/20 (100%) |
| REDOWNLOADS | 20/20 (100%) |
| TOTAL_DOWNLOADS | 20/20 (100%) |
| ACTIVE_DEVICES | 20/20 (100%) |
| ACTIVE_DEVICES_LAST_30_DAYS | 20/20 (100%) |
| DELETIONS | 20/20 (100%) |
| INSTALLATIONS | 20/20 (100%) |
| SESSIONS | 20/20 (100%) |

**Sample extra rows in Predicted:**
- 2020-11-27 / App Store Browse / iPhone
- 2020-12-22 / Web Referrer / iPod
- 2021-01-04 / App Store Search / Desktop
- 2021-01-09 / Web Referrer / iPad
- 2021-02-19 / App Store Browse / iPad

**Impact:**
* Current implementation: **20/40 row matches (50.0%)** - 20 extra rows
* Corrected implementation would: **20/20 matches (100%)**

---

## Result
**Column values are correct for matching rows, but predicted includes double the rows**

**Key insight:**
The FULL OUTER JOIN approach generates rows for every date/device/source_type combination that exists in ANY source table. The ground truth only includes combinations where meaningful primary data exists. The fix requires more restrictive joins or post-join filtering to eliminate sparse data rows.
