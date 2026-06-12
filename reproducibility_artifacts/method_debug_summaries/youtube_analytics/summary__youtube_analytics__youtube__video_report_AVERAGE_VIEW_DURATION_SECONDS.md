# Column Mismatch Summary

## Database: youtube_analytics
## Table: youtube__video_report
## Column: AVERAGE_VIEW_DURATION_SECONDS

**Description:**
Average duration of views for the video in seconds.

---

## Root Cause
**Missing aggregation: Multiple source rows per (date, video) not aggregated**

### Incorrect SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    cb.average_view_duration_seconds  -- No aggregation
FROM channel_basic cb
```

### Correct SQL Logic
```sql
SELECT
    cb.date_day,
    cb.video_id,
    -- Weighted average by views
    SUM(cb.average_view_duration_seconds * cb.views) / NULLIF(SUM(cb.views), 0)
        AS average_view_duration_seconds
FROM channel_basic cb
GROUP BY cb.date_day, cb.video_id
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Average view duration should be aggregated per (date, video) combination
  * GT shows one value per date+video

* **What the SQL actually computes:**
  * Returns raw rows without aggregation
  * Multiple rows per (date, video) due to different dimensions in source

* **Schema insight:**
  * Source `channel_basic` has multiple rows per (date, video_id)
  * GT has 454 rows, Pred has 1000 rows

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Video | Source Rows | GT (Aggregated) |
| ---- | ----- | ----------- | --------------- |
| 2021-07-27 | -serQUrgefU | 8.9s, 14.872s | 11.886s |

**Calculation:**
- (8.9*1 + 14.872*1) / (1+1) = 11.886 seconds (matches GT)

**Impact:**
* Current implementation: **0/454 matches (0%)**
* Corrected implementation: **454/454 matches (100%)**

---

## Result

**Perfect match with corrected logic (weighted average aggregation)**
