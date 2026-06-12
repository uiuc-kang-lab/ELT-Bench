# Column Mismatch Summary

## Database: apple_store
## Table: apple_store__overview_report
## Columns: DATE_DAY, APP_ID, APP_NAME, IMPRESSIONS, PAGE_VIEWS, CRASHES, FIRST_TIME_DOWNLOADS, REDOWNLOADS, TOTAL_DOWNLOADS, ACTIVE_DEVICES, DELETIONS, INSTALLATIONS, SESSIONS

### Description
Each record represents daily metrics for each app_id (aggregated across all source types and devices).

---

## Root Cause
**Granularity mismatch: Predicted SQL generates 4x the rows via FULL OUTER JOINs, including dates where only partial data exists**

### Incorrect SQL Logic
```sql
SELECT
    COALESCE(asd.date_day, dd.date_day, ud.date_day, ca.date_day) AS date_day,
    COALESCE(asd.app_id, dd.app_id, ud.app_id, ca.app_id) AS app_id,
    a.app_name,
    COALESCE(asd.impressions, 0) AS impressions,
    ...
FROM app_store_device asd
FULL OUTER JOIN downloads_device dd ON asd.date_day = dd.date_day AND asd.app_id = dd.app_id
FULL OUTER JOIN usage_device ud ON ...
FULL OUTER JOIN crashes_app_version ca ON ...
```

### Correct SQL Logic
```sql
-- Use INNER JOINs between primary source tables
-- Or filter to dates where primary metrics (impressions/downloads) exist
-- GT only includes dates where meaningful aggregated data exists
```

---

## Why the Original Logic Is Wrong

* **What GT expects**: 9 rows with specific dates where meaningful daily overview data exists.

* **What the SQL computes**: FULL OUTER JOINs across 4 aggregated source tables generate 37 rows, including every date where ANY metric exists in ANY source table.

* **Date filtering difference**:
  - GT dates (9): 2020-11-15, 2021-02-24, 2021-03-17, 2021-06-06, 2021-06-24, 2021-07-12, 2021-08-23, 2021-10-03, 2021-10-06
  - Predicted dates (37): Includes 28 additional dates from various source tables

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Ground Truth | Predicted |
| ------ | ------------ | --------- |
| Total rows | 9 | 37 |
| Matching rows | 9 | 9 |
| Extra rows in Pred | 0 | 28 |

**For the 9 matching rows, ALL column values match perfectly:**

| Column | Match Rate |
| ------ | ---------- |
| APP_NAME | 9/9 (100%) |
| IMPRESSIONS | 9/9 (100%) |
| PAGE_VIEWS | 9/9 (100%) |
| CRASHES | 9/9 (100%) |
| FIRST_TIME_DOWNLOADS | 9/9 (100%) |
| REDOWNLOADS | 9/9 (100%) |
| TOTAL_DOWNLOADS | 9/9 (100%) |
| ACTIVE_DEVICES | 9/9 (100%) |
| DELETIONS | 9/9 (100%) |
| INSTALLATIONS | 9/9 (100%) |
| SESSIONS | 9/9 (100%) |

**Sample extra dates in Predicted:**
- 2020-11-27
- 2020-12-05
- 2020-12-21
- 2020-12-22
- 2021-01-04
- ... (28 additional dates)

**Impact:**
* Current implementation: **9/37 row matches (24.3%)** - 28 extra rows
* Corrected implementation would: **9/9 matches (100%)**

---

## Result
**Column values are correct for matching rows, but predicted includes 4x the rows**

**Key insight:**
The overview report should only include dates where meaningful aggregated data exists across the primary metrics. The FULL OUTER JOIN approach includes every date where ANY single metric exists, creating many rows with mostly zero values. The fix requires either:
1. Using INNER JOINs with the primary app_store_device table as the base
2. Adding a WHERE clause to filter out rows where primary metrics are zero
3. Only including dates that appear in a specific "authoritative" source table
