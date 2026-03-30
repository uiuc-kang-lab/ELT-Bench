# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
## Column: CAMPAIGN_ID

**Description:**
The ID of the campaign.

---

## Root Cause
**Row ordering difference: Values are swapped between rows due to non-deterministic GROUP BY ordering**

### Current SQL Logic
```sql
SELECT
    ...
    ap.campaign_id,
    ...
FROM ad_performance ap
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
```

### Note on Issue
The SQL logic is semantically correct. Campaign IDs are passed through correctly, but rows appear in different order.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * ID of the campaign associated with the ad performance

* **What the SQL actually computes:**
  * Correctly passes through campaign_id from source
  * Value distribution matches GT exactly
  * Row-level mismatches are due to ordering

**Value distribution (both GT and Predicted):**
| CAMPAIGN_ID | Count |
| ----------- | ----- |
| 349886460 | 185 |
| 349886459 | 72 |
| 359751135 | 55 |

---

## Evidence

**Key comparison demonstrating the issue:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Row-by-row match | 235/312 | 75.3% |

**Sample mismatches (IDs swapped between rows):**
| Index | GT CAMPAIGN_ID | Predicted CAMPAIGN_ID |
| ----- | -------------- | --------------------- |
| 37 | 349886459 | 349886460 |
| 38 | 349886460 | 349886459 |
| 41 | 349886460 | 349886459 |
| 42 | 349886459 | 349886460 |

**Impact:**
* Current implementation: **235/312 matches (75.3%)**
* Total per-campaign counts match exactly

---

## Result

**Row ordering issue - not a calculation error**

The CAMPAIGN_ID is correctly passed through. Mismatches are due to rows being in different order.
