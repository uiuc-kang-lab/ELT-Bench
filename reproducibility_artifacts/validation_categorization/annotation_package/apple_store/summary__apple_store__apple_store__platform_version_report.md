# Column Mismatch Summary

## Database: apple_store
## Table: apple_store__platform_version_report
## Columns: DATE_DAY, APP_ID, APP_NAME, SOURCE_TYPE, PLATFORM_VERSION, IMPRESSIONS, IMPRESSIONS_UNIQUE_DEVICE, PAGE_VIEWS, PAGE_VIEWS_UNIQUE_DEVICE, CRASHES, FIRST_TIME_DOWNLOADS, REDOWNLOADS, TOTAL_DOWNLOADS, ACTIVE_DEVICES, ACTIVE_DEVICES_LAST_30_DAYS, DELETIONS, INSTALLATIONS, SESSIONS

### Description
Each record represents daily metrics for each app_id, source_type and platform version.

---

## Root Cause
**Granularity mismatch: Predicted SQL generates extra rows via FULL OUTER JOINs, and has date misalignment between source tables**

### Incorrect SQL Logic
```sql
SELECT
    COALESCE(aspv.date_day, dpv.date_day, upv.date_day, cpv.date_day) AS date_day,
    COALESCE(aspv.app_id, dpv.app_id, upv.app_id, cpv.app_id) AS app_id,
    COALESCE(aspv.source_type, dpv.source_type, upv.source_type, 'Null') AS source_type,
    COALESCE(aspv.platform_version, dpv.platform_version, upv.platform_version, cpv.platform_version) AS platform_version,
    ...
FROM app_store_platform_version aspv
FULL OUTER JOIN downloads_platform_version dpv ON ...
FULL OUTER JOIN usage_platform_version upv ON ...
FULL OUTER JOIN crashes_platform_version cpv ON ...
```

### Correct SQL Logic
```sql
-- Use more restrictive joins or filter criteria to match GT row selection
-- GT has specific date/source_type/platform_version combinations
-- that don't include all FULL OUTER JOIN results
```

---

## Why the Original Logic Is Wrong

* **What GT expects**: 20 rows with specific date/app_id/source_type/platform_version combinations.

* **What the SQL computes**: FULL OUTER JOINs across 4 source tables generate 31 rows, including combinations where data exists in only one source table.

* **Additional issue**: 2 rows exist in GT but not in Predicted (2021-05-11 and 2021-05-28 with Null source_type), suggesting the crash data or usage data aggregation differs.

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total rows | 20 | 31 |
| Matching rows | 18 | 18 |
| GT only rows | 2 | 0 |
| Pred only rows | 0 | 13 |

**For the 18 matching rows, ALL column values match perfectly:**

| Column | Match Rate |
| ------ | ---------- |
| APP_NAME | 18/18 (100%) |
| IMPRESSIONS | 18/18 (100%) |
| IMPRESSIONS_UNIQUE_DEVICE | 18/18 (100%) |
| PAGE_VIEWS | 18/18 (100%) |
| PAGE_VIEWS_UNIQUE_DEVICE | 18/18 (100%) |
| CRASHES | 18/18 (100%) |
| FIRST_TIME_DOWNLOADS | 18/18 (100%) |
| REDOWNLOADS | 18/18 (100%) |
| TOTAL_DOWNLOADS | 18/18 (100%) |
| ACTIVE_DEVICES | 18/18 (100%) |
| ACTIVE_DEVICES_LAST_30_DAYS | 18/18 (100%) |
| DELETIONS | 18/18 (100%) |
| INSTALLATIONS | 18/18 (100%) |
| SESSIONS | 18/18 (100%) |

**Rows in GT only (missing from Predicted):**
- 2021-05-11 / app 12345 / Null source_type / iOS 1.0
- 2021-05-28 / app 12345 / Null source_type / iOS 1.0

**Sample extra rows in Predicted:**
- 2021-01-30 / Web Referrer
- 2021-04-05 / App Store Search
- 2021-04-06 / App Store Search

**Impact:**
* Current implementation: **18/31 row matches (58.1%)** - 2 missing + 13 extra
* Corrected implementation would: **20/20 matches (100%)**

---

## Result
**Column values are correct for matching rows, but row set differs**

**Key insight:**
The FULL OUTER JOIN creates extra rows and may be missing some rows due to join condition or aggregation differences. The 2 missing GT rows suggest the crashes or usage data aggregation may not capture all Null source_type entries.
