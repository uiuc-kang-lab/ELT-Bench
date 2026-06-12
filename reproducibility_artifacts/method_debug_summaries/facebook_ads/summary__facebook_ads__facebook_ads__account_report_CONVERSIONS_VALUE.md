# Column Mismatch Summary

## Database: facebook_ads
## Table: facebook_ads__account_report
## Column: CONVERSIONS_VALUE

**Description:**
Total monetary of conversions using the default attribution window on the given day. Set to 0 if the value is NULL.

---

## Root Cause
**Overly restrictive action_type filter: SQL only includes `offsite_conversion.fb_pixel_purchase` but GT includes all action_types except `offsite_conversion.fb_pixel_view_content`**

### Incorrect SQL Logic
```sql
conversion_values_agg AS (
    SELECT
        ad_id,
        date,
        SUM(COALESCE(value, 0)) as total_conversion_values
    FROM basic_ad_action_values
    WHERE action_type = 'offsite_conversion.fb_pixel_purchase'
    GROUP BY ad_id, date
)
```

### Correct SQL Logic
```sql
conversion_values_agg AS (
    SELECT
        ad_id,
        date,
        SUM(COALESCE(value, 0)) as total_conversion_values
    FROM basic_ad_action_values
    WHERE action_type != 'offsite_conversion.fb_pixel_view_content'
    GROUP BY ad_id, date
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Total monetary value of all conversion-related actions for the account
  * Should include purchases, add-to-cart, and other conversion events
  * Should exclude view-related metrics

* **What the SQL actually computes:**
  * Only includes `offsite_conversion.fb_pixel_purchase` action_type
  * Misses other valid conversion types like `onsite_conversion.purchase`, `onsite_web_add_to_cart`, `view_content`

**Schema verification:**
- `basic_ad_action_values.action_type`: "The kind of actions taken on your ad"
- `basic_ad_action_values.value`: "Monetary value associated with the conversion action"

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Account ID | Wrong Logic | Correct Logic | Ground Truth |
| ---- | ---------- | ----------- | ------------- | ------------ |
| 2020-12-03 | 1700252260223815 | 29324.84 | 29324.84 | 29324.84 |
| 2020-12-05 | 1700252260223815 | 0.0 | 4194.29 | 4194.29 |
| 2020-12-13 | 1700252260223815 | 0.0 | 29324.84 | 29324.84 |
| 2020-12-14 | 1700252260223815 | 0.0 | 29324.84 | 29324.84 |

**Impact:**
* Current implementation: **6/9 matches (66.7%)**
* Corrected implementation: **9/9 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is identical to the campaign_report: `conversions_value` should sum all conversion-related monetary values except `offsite_conversion.fb_pixel_view_content`.
