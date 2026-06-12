# Column Mismatch Summary

## Database: facebook_ads
## Table: facebook_ads__account_report
## Column: CONVERSIONS

**Description:**
Total number of conversions using the default attribution window on the given day. Set to 0 if the value is NULL.

---

## Root Cause
**Wrong action_type filter: SQL filters basic_ad_actions by `offsite_conversion.fb_pixel_purchase` which doesn't exist in the table; correct action_type is `offsite_conversion.fb_pixel_lead`**

### Incorrect SQL Logic
```sql
conversions_agg AS (
    SELECT
        ad_id,
        date,
        SUM(COALESCE(value, 0)) as total_conversions
    FROM basic_ad_actions
    WHERE action_type = 'offsite_conversion.fb_pixel_purchase'
    GROUP BY ad_id, date
)
```

### Correct SQL Logic
```sql
conversions_agg AS (
    SELECT
        ad_id,
        date,
        SUM(COALESCE(value, 0)) as total_conversions
    FROM basic_ad_actions
    WHERE action_type = 'offsite_conversion.fb_pixel_lead'
    GROUP BY ad_id, date
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Total number of conversions (lead conversions) for the account on each day
  * Conversions are tracked in the `basic_ad_actions` table with the `value` column

* **What the SQL actually computes:**
  * Filters `basic_ad_actions` by `action_type = 'offsite_conversion.fb_pixel_purchase'`
  * This action_type does NOT exist in `basic_ad_actions` (only in `basic_ad_action_values`)
  * Result: always returns 0 conversions

**Schema verification:**
- `basic_ad_actions.action_type`: "The kind of actions taken on your ad"
- `basic_ad_actions.value`: "Conversion metric value using the default attribution window"

**Action types in basic_ad_actions:**
- `offsite_conversion.fb_pixel_lead`: 8 records ← Correct action type
- `lead`: 2 records
- `offsite_conversion.fb_pixel_purchase`: 0 records ← Wrong (doesn't exist!)

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Account ID | Wrong Logic (purchase) | Correct Logic (lead) | Ground Truth |
| ---- | ---------- | ---------------------- | -------------------- | ------------ |
| 2020-12-02 | 1700252260223815 | 0.0 | 2.0 | 2.0 |
| 2020-12-03 | 1700252260223815 | 0.0 | 3.0 | 3.0 |
| 2020-12-05 | 1700252260223815 | 0.0 | 2.0 | 2.0 |
| 2020-12-13 | 1700252260223815 | 0.0 | 4.0 | 4.0 |

**Impact:**
* Current implementation: **5/9 matches (55.6%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is identical to the campaign_report: the `basic_ad_actions` table tracks lead conversions with action_type `offsite_conversion.fb_pixel_lead`, not `offsite_conversion.fb_pixel_purchase`.
