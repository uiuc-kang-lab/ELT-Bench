# Column Mismatch Summary

## Database: facebook_ads
## Table: facebook_ads__ad_report
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
  * Total monetary value of all conversion-related actions for the ad
  * Should include purchases, add-to-cart, and other conversion events
  * Should exclude view-related metrics

* **What the SQL actually computes:**
  * Only includes `offsite_conversion.fb_pixel_purchase` action_type
  * Misses other valid conversion types like `onsite_conversion.purchase`, `onsite_web_add_to_cart`, `view_content`

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Ad ID | Action Type | Value | Wrong Logic | Correct Logic | GT |
| ---- | ----- | ----------- | ----- | ----------- | ------------- | -- |
| 2020-12-03 | 6229007992271 | offsite_conversion.fb_pixel_purchase | 29324.84 | 29324.84 | 29324.84 | 29324.84 |
| 2020-12-05 | 6229007992271 | view_content | 4194.29 | 0.0 | 4194.29 | 4194.29 |
| 2020-12-08 | 6229007992271 | offsite_conversion.fb_pixel_view_content | 4194.29 | 0.0 | 0.0 | 0.0 |
| 2020-12-13 | 6229007992271 | onsite_conversion.purchase | 29324.84 | 0.0 | 29324.84 | 29324.84 |
| 2020-12-14 | 6229007992271 | onsite_web_add_to_cart | 29324.84 | 0.0 | 29324.84 | 29324.84 |

**Impact:**
* Current implementation: **7/10 matches (70.0%)**
* Corrected implementation: **10/10 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is identical to other reports: `conversions_value` should sum all conversion-related monetary values except `offsite_conversion.fb_pixel_view_content`.

**Included action_types:**
- `offsite_conversion.fb_pixel_purchase` (purchases)
- `onsite_conversion.purchase` (purchases)
- `onsite_web_add_to_cart` (cart additions)
- `view_content` (content views that led to conversion value)

**Excluded action_types:**
- `offsite_conversion.fb_pixel_view_content` (pixel view tracking, not a conversion)
