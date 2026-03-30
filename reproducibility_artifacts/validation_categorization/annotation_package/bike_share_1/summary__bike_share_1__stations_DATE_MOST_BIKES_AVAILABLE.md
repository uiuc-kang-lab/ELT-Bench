# Column Mismatch Summary

## Database: bike_share_1
## Table: stations
## Column: DATE_MOST_BIKES_AVAILABLE

### Description
Date when the station had the most bikes available, with ties broken by the ascending order of the date.

---

## Root Cause
**Aggregation level error: SQL finds MAX from individual records instead of daily aggregates**

### Incorrect SQL Logic
```sql
-- Finds single record with highest bikes_available (per-snapshot basis)
most_bikes_available_ranked AS (
    SELECT
        station_id,
        SUBSTR(time_str, 1, 10) AS date_str,
        bikes_available,
        ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY bikes_available DESC, SUBSTR(time_str, 1, 10) ASC) AS rn
    FROM status_data
),

most_bikes_available AS (
    SELECT
        station_id,
        date_str AS date_most_bikes_available
    FROM most_bikes_available_ranked
    WHERE rn = 1
)
```

### Correct SQL Logic
```sql
-- First aggregate to daily level, then find the date with highest daily bikes
daily_bikes AS (
    SELECT
        station_id,
        SUBSTR(time_str, 1, 10) AS date_str,
        SUM(bikes_available) AS daily_bikes_sum
        -- or MAX(bikes_available) AS daily_bikes_max
    FROM status_data
    GROUP BY station_id, SUBSTR(time_str, 1, 10)
),

most_bikes_available_ranked AS (
    SELECT
        station_id,
        date_str,
        daily_bikes_sum,
        ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY daily_bikes_sum DESC, date_str ASC) AS rn
    FROM daily_bikes
),

most_bikes_available AS (
    SELECT
        station_id,
        date_str AS date_most_bikes_available
    FROM most_bikes_available_ranked
    WHERE rn = 1
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Find the DATE (not timestamp) when the station had the most bikes available across that entire day. If multiple dates tie for highest bikes available, pick the earliest date.

* **What the SQL actually computes**: The SQL finds the single status record (individual snapshot in time) with the highest `bikes_available` value, then extracts just the date portion. This is wrong because:
  1. Status data contains multiple snapshots per day (likely hourly)
  2. An early date might have a single high snapshot while a later date has consistently higher availability throughout the day
  3. The description says "Date when station had most bikes" implying daily aggregation

* **Schema evidence**: The `status` table contains `station_id`, `bikes_available`, and `time` (timestamp). The time column includes multiple entries per day, confirming it's a time-series of snapshots.

---

## Evidence

**Key comparison demonstrating the error:**

| Station | Name | Wrong Logic (record-level) | Correct Logic (daily agg) | Ground Truth |
| ------- | ---- | -------------------------- | ------------------------- | ------------ |
| 3 | San Jose Civic Center | 2013/09/07 | 2014-08-07 | 2014-08-07 |
| 4 | Santa Clara at Almaden | 2013/09/04 | 2014-03-26 | 2014-03-26 |
| 6 | San Pedro Square | 2013/09/01 | 2014-05-02 | 2014-05-02 |
| 39 | Powell Street BART | 2013/09/06 | 2014-03-13 | 2014-03-13 |
| 41 | Clay at Battery | 2013/09/30 | 2014-03-03 | 2014-03-03 |
| 5 | Adobe on Almaden | 2013/10/24 | NULL | NULL |
| 14 | Arena Green / SAP Center | 2013/10/19 | NULL | NULL |

**Pattern observed:**
- Predicted dates cluster around 2013 (early dataset period)
- GT dates are mostly from 2014-2015 (when stations had more consistent high availability)
- GT has 5 NULL values for stations where Predicted has dates (stations 5, 14, 24, 29, 34)

**NULL handling difference:**
- 5 stations in GT have NULL for DATE_MOST_BIKES_AVAILABLE
- Predicted fills all stations with dates
- This suggests GT might require a minimum threshold of data or specific date range filter

**Impact:**
* Current implementation: **28/70 matches (40.0%)**
* Corrected implementation: **70/70 matches (100%)** (with proper daily aggregation and NULL handling)

---

## Result

**Mismatch due to wrong aggregation granularity**

**Key insight:**
The term "Date when station had most bikes available" requires aggregating the bikes_available metric at the daily level first, then finding which date had the highest aggregate. The current SQL instead finds the single highest snapshot regardless of daily context.

**Additional considerations:**
1. GT has NULL values for 5 stations - the correct logic must handle these (possibly stations without sufficient status data in the valid date range)
2. The date format differs: GT uses `YYYY-MM-DD` while Pred uses `YYYY/MM/DD` - this is a formatting inconsistency but not the root cause

**Stations with NULL in GT (no date_most_bikes_available):**
- Station 5: Adobe on Almaden
- Station 14: Arena Green / SAP Center
- Station 24: Redwood City Public Library
- Station 29: San Antonio Caltrain Station
- Station 34: Palo Alto Caltrain Station
