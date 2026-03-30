# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__video_report
## Column: VIEWS

**Description:**
Total number of views the video received.

---

## Root Cause
**Missing aggregation: Multiple source rows per (date, video) not summed**

### Incorrect SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    cb.views  -- No aggregation
FROM channel_basic cb
```

### Correct SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    SUM(cb.views) AS views
FROM channel_basic cb
GROUP BY cb.date_day, cb.video_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Total views should be summed per (date, video) combination

* **What the SQL actually computes:**
  * Returns individual rows without aggregation
  * Multiple rows per (date, video) due to different dimensions

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Video | Source Rows (views) | GT (Sum) |
| ---- | ----- | ------------------- | -------- |
| 2021-07-27 | -serQUrgefU | 1, 1 | 2 |

**Impact:**
* Current implementation: **~25%** (only single-row date+video combos match)
* Corrected implementation: **454/454 matches (100%)**

---

## Result

**Perfect match with SUM aggregation**
