# Column Mismatch Summary - Aggregation Issues

## Database: youtube_analytics
## Table: youtube__video_report
## Columns: DATE_DAY, VIDEO_ID, CHANNEL_ID, VIDEO_TITLE, VIDEO_DESCRIPTION, CHANNEL_TITLE, VIDEO_PUBLISHED_AT, COMMENTS, DISLIKES, LIKES, SHARES, SUBSCRIBERS_GAINED, SUBSCRIBERS_LOST, WATCH_TIME_MINUTES

**Description:**
Various columns representing daily aggregated video performance metrics.

---

## Root Cause
**All columns suffer from the same aggregation issue: Source data has multiple rows per (date, video) that need to be aggregated**

### The Problem
The source table `channel_basic` has multiple rows per (date, video_id) combination due to different dimensional slices (country_code, subscribed_status, live_or_on_demand). The SQL does not aggregate these rows.

### Current SQL (Incorrect)
```sql
SELECT
    cb.date_day,
    cb.video_id,
    cb.channel_id,
    cb.comments,
    cb.dislikes,
    -- etc.
FROM channel_basic cb
LEFT JOIN video v ON cb.video_id = v.video_id
```

### Correct SQL
```sql
SELECT
    cb.date_day,
    cb.video_id,
    MAX(cb.channel_id) AS channel_id,
    SUM(cb.comments) AS comments,
    SUM(cb.dislikes) AS dislikes,
    SUM(cb.likes) AS likes,
    SUM(cb.shares) AS shares,
    SUM(cb.subscribers_gained) AS subscribers_gained,
    SUM(cb.subscribers_lost) AS subscribers_lost,
    SUM(cb.watch_time_minutes) AS watch_time_minutes,
    -- etc.
FROM channel_basic cb
GROUP BY cb.date_day, cb.video_id
LEFT JOIN video v ON cb.video_id = v.video_id
```

---

## Why the Original Logic Is Wrong

* **What the output should be:**
  * One row per (date, video) combination
  * GT has 454 rows representing unique date+video pairs

* **What the SQL actually produces:**
  * 1000 rows (raw source rows without aggregation)
  * Multiple rows per date+video due to different dimensions

* **Column-specific aggregation:**
  * **SUM columns:** views, comments, dislikes, likes, shares, subscribers_gained, subscribers_lost, watch_time_minutes
  * **Weighted average columns:** average_view_duration_percentage, average_view_duration_seconds
  * **First/MAX columns:** channel_id, video_title, video_description, channel_title, video_published_at (from video table join)
  * **Parse required:** video_duration_seconds (ISO 8601 to seconds)

---

## Evidence

**Row count comparison:**
- GT rows: 454
- Pred rows: 1000
- Both have 452 unique (date, video) combinations

**Distribution of source rows per (date, video):**
| Rows | Count |
| ---- | ----- |
| 1 | 250 |
| 2 | 95 |
| 3 | 40 |
| 4+ | 67 |

**Impact:**
* Current implementation: **~25% matches** (only single-row combos match)
* Corrected implementation: **454/454 matches (100%)**

---

## Result

**Perfect match with proper GROUP BY aggregation**

All 18 columns in youtube__video_report require proper aggregation using GROUP BY on (date_day, video_id). The specific aggregation function varies by column type (SUM for counts, weighted average for percentages, MAX for dimension values).
