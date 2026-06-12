# Column Mismatch Summary

## Database: apple_store
## Table: apple_store__device_report
## Column: TOTAL_DOWNLOADS

### Description
See table-level summary

---

## Root Cause
### 1. FULL OUTER JOIN Creates Extra Rows

**Problem**: The predicted SQL uses FULL OUTER JOINs between multiple source tables, which creates extra row combinations when data exists in one table but not others.

**Example from `apple_store__source_type_report.sql`**:
```sql
FROM app_store_device asd
FULL OUTER JOIN downloads_device dd
    ON asd.date_day = dd.date_day
    AND asd.app_id = dd.app_id
    AND asd.source_type = dd.source_type
FULL OUTER JOIN usage_device ud
    ...
```

**Impact**:
- Source tables have different date/source_type combinations
- FULL OUTER JOIN creates rows for ALL combinations that exist in ANY table
- GT only includes rows where specific criteria are met

### 2. SOURCE_TYPE Value Handling Mismatch

**Problem**:
- Ground truth uses **empty string** (`''`) for missing/null source types
- Predicted SQL uses **'Null' string** via `COALESCE(..., 'Null')`

**Example**:
| GT SOURCE_TYPE | Predicted SOURCE_TYPE |
|----------------|----------------------|
| (empty string) | Null |
| App Store Browse | App Store Browse |

**SQL Causing Issue**:
```sql
COALESCE(asd.source_type, dd.source_type, ud.source_type, 'Null') AS source_type
```

### 3. Data Type Mismatch (APP_ID)

**Problem**: APP_ID appears as float (`12345.0`) in predicted output vs integer (`12345`) in ground truth.

**Cause**: Pandas inference or SQL casting when reading/writing CSV files.

---

## Evidence


---

## Result

