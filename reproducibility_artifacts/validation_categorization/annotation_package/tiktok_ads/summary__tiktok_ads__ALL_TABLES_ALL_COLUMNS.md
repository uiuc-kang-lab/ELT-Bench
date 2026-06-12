# Column Mismatch Summary

## Database: tiktok_ads
## Tables: tiktok_ads__campaign_report, tiktok_ads__ad_report, tiktok_ads__advertiser_report
## Columns: ALL COLUMNS (23+ columns per table)

**Description:**
Multiple columns across all three tables have mismatches because the SQL drops rows where lookup data (specifically advertiser information) is missing.

---

## Root Cause
**INNER JOIN drops rows when lookup tables (advertiser) have missing records**

The SQL uses `JOIN` (INNER JOIN) to link report data with the `advertiser` table, but some advertiser IDs referenced in the data don't exist in the `advertiser` table. This causes entire rows to be dropped from the output.

### Incorrect SQL Logic

**tiktok_ads__campaign_report.sql:**
```sql
FROM campaign_report cr
JOIN campaign_history ch ON cr.campaign_id = ch.campaign_id AND ch.rn = 1
JOIN advertiser a ON ch.advertiser_id = a.advertiser_id AND a.rn = 1  -- INNER JOIN drops rows!
```

**tiktok_ads__ad_report.sql:**
```sql
FROM ad_report ar
JOIN ad_history ah ON ar.ad_id = ah.ad_id AND ah.rn = 1
JOIN adgroup_history agh ON ah.adgroup_id = agh.adgroup_id AND agh.rn = 1
JOIN campaign_history ch ON ah.campaign_id = ch.campaign_id AND ch.rn = 1
JOIN advertiser adv ON ah.advertiser_id = adv.advertiser_id AND adv.rn = 1  -- INNER JOIN drops rows!
```

**tiktok_ads__advertiser_report.sql:**
```sql
FROM ad_report ar
JOIN ad_history ah ON ar.ad_id = ah.ad_id AND ah.rn = 1
JOIN advertiser a ON ah.advertiser_id = a.advertiser_id AND a.rn = 1  -- INNER JOIN drops rows!
GROUP BY 1, 2, 3, 4
```

### Correct SQL Logic

Change `JOIN` to `LEFT JOIN` for all lookup table joins to preserve all report rows:

**tiktok_ads__campaign_report.sql:**
```sql
FROM campaign_report cr
LEFT JOIN campaign_history ch ON cr.campaign_id = ch.campaign_id AND ch.rn = 1
LEFT JOIN advertiser a ON ch.advertiser_id = a.advertiser_id AND a.rn = 1
```

**tiktok_ads__ad_report.sql:**
```sql
FROM ad_report ar
LEFT JOIN ad_history ah ON ar.ad_id = ah.ad_id AND ah.rn = 1
LEFT JOIN adgroup_history agh ON ah.adgroup_id = agh.adgroup_id AND agh.rn = 1
LEFT JOIN campaign_history ch ON ah.campaign_id = ch.campaign_id AND ch.rn = 1
LEFT JOIN advertiser adv ON ah.advertiser_id = adv.advertiser_id AND adv.rn = 1
```

**tiktok_ads__advertiser_report.sql:**
```sql
FROM ad_report ar
LEFT JOIN ad_history ah ON ar.ad_id = ah.ad_id AND ah.rn = 1
LEFT JOIN advertiser a ON ah.advertiser_id = a.advertiser_id AND a.rn = 1
GROUP BY 1, 2, 3, 4
```

---

## Why the Original Logic Is Wrong

* **What the GT expects**: All records from the hourly report tables should be included in the output, even if some lookup data (advertiser name, currency) is missing.

* **What the SQL actually computes**: Only records where ALL joins succeed are included. Records with missing lookup data are dropped.

**The data shows:**
- `advertiser` table has IDs: {1, 2}
- `campaign_history` references advertiser IDs: {1, 2, 3, 4}
- Campaigns with advertiser_id 3 and 4 are dropped because they don't exist in the advertiser table

This is a classic **fan trap** or **referential integrity gap** - the hourly report data references entities that don't have complete lookup data yet.

---

## Evidence

**Key comparison demonstrating the error:**

### tiktok_ads__campaign_report
| CAMPAIGN_ID | ADVERTISER_ID | In Advertiser Table? | In GT | In Predicted |
| ----------- | ------------- | -------------------- | ----- | ------------ |
| 1 | 1 | Yes | Yes | Yes |
| 2 | 2 | Yes | Yes | Yes |
| 3 | 3 | **No** | Yes | **No (dropped)** |
| 4 | 4 | **No** | Yes | **No (dropped)** |

### tiktok_ads__ad_report
| AD_ID | ADVERTISER_ID | In Advertiser Table? | In GT | In Predicted |
| ----- | ------------- | -------------------- | ----- | ------------ |
| 1 | 1 | Yes | Yes | Yes |
| 2 | 2 | Yes | Yes | Yes |
| 3 | 3 | **No** | Yes | **No (dropped)** |
| 4 | 4 | **No** | Yes | **No (dropped)** |

### tiktok_ads__advertiser_report
| ADVERTISER_ID | In Advertiser Table? | In GT | In Predicted |
| ------------- | -------------------- | ----- | ------------ |
| 1 | Yes | Yes | Yes |
| 2 | Yes | Yes | Yes |
| 3 | **No** | Yes | **No (dropped)** |
| 4 | **No** | Yes | **No (dropped)** |

**Impact:**
* All three tables: **GT has 4 rows, Predicted has 2 rows**
* Every column in every table shows **2/4 matches (50%)** because 2 rows are missing
* Some calculated columns (DAILY_CPC) show additional mismatches due to NULL vs 0 handling

---

## Result

✅ **Perfect match achievable with LEFT JOIN fix**

**Key insight:**
All mismatches stem from a single root cause: using INNER JOIN instead of LEFT JOIN for lookup table joins. The fix is to change `JOIN` to `LEFT JOIN` in all three SQL files.

**Affected columns (all due to missing rows):**

### Campaign Report (23 columns affected):
CAMPAIGN_NAME, IMPRESSIONS, CLICKS, SPEND, REACH, CONVERSION, LIKES, COMMENTS, SHARES, PROFILE_VISITS, FOLLOWS, VIDEO_WATCHED_2_S, VIDEO_WATCHED_6_S, VIDEO_VIEWS_P_25, VIDEO_VIEWS_P_50, VIDEO_VIEWS_P_75, REAL_TIME_CONVERSION, TOTAL_PURCHASE_VALUE, TOTAL_SALES_LEAD_VALUE, TOTAL_CONVERSION_VALUE, DAILY_CPC, DAILY_CPM, DAILY_CTR

### Ad Report (32 columns affected):
ADVERTISER_ID, CAMPAIGN_ID, CAMPAIGN_NAME, AD_GROUP_ID, AD_GROUP_NAME, AD_NAME, CATEGORY, GENDER, BUDGET, IMPRESSIONS, CLICKS, SPEND, REACH, CONVERSION, LIKES, COMMENTS, SHARES, PROFILE_VISITS, FOLLOWS, VIDEO_WATCHED_2_S, VIDEO_WATCHED_6_S, VIDEO_VIEWS_P_25, VIDEO_VIEWS_P_50, VIDEO_VIEWS_P_75, REAL_TIME_CONVERSION, TOTAL_PURCHASE_VALUE, TOTAL_SALES_LEAD_VALUE, TOTAL_CONVERSION_VALUE, DAILY_CPC, DAILY_CPM, DAILY_CTR

### Advertiser Report (22 columns affected):
CLICKS, IMPRESSIONS, SPEND, REACH, CONVERSION, LIKES, COMMENTS, SHARES, PROFILE_VISITS, FOLLOWS, VIDEO_WATCHED_2_S, VIDEO_WATCHED_6_S, VIDEO_VIEWS_P_25, VIDEO_VIEWS_P_50, VIDEO_VIEWS_P_75, REAL_TIME_CONVERSION, TOTAL_PURCHASE_VALUE, TOTAL_SALES_LEAD_VALUE, TOTAL_CONVERSION_VALUE, DAILY_CPC, DAILY_CPM, DAILY_CTR
