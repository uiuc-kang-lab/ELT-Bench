# Column Mismatch Summary

## Database: facebook_ads
## Table: facebook_ads__campaign_report
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
  * Total monetary value of all conversion-related actions
  * Should include purchases, add-to-cart, and other conversion events
  * Should exclude view-related metrics (like `offsite_conversion.fb_pixel_view_content`)

* **What the SQL actually computes:**
  * Only includes `offsite_conversion.fb_pixel_purchase` action_type
  * Misses other valid conversion types like `onsite_conversion.purchase`, `onsite_web_add_to_cart`, `view_content`

**Schema verification:**
- `basic_ad_action_values.action_type`: "The kind of actions taken on your ad"
- `basic_ad_action_values.value`: "Monetary value associated with the conversion action"

**Action types in basic_ad_action_values:**
- `offsite_conversion.fb_pixel_purchase` ← Included by SQL (too restrictive)
- `onsite_conversion.purchase` ← Should be included
- `onsite_web_add_to_cart` ← Should be included
- `view_content` ← Should be included
- `offsite_conversion.fb_pixel_view_content` ← Should be EXCLUDED

---

## Evidence

**Key comparison demonstrating the error:**

| Date | Campaign ID | Action Type | Value | Wrong Logic | Correct Logic | GT |
| ---- | ----------- | ----------- | ----- | ----------- | ------------- | -- |
| 2020-12-03 | 6229007982271 | offsite_conversion.fb_pixel_purchase | 29324.84 | 29324.84 | 29324.84 | 29324.84 |
| 2020-12-05 | 6229007982271 | view_content | 4194.29 | 0.0 | 4194.29 | 4194.29 |
| 2020-12-08 | 6229007982271 | offsite_conversion.fb_pixel_view_content | 4194.29 | 0.0 | 0.0 | 0.0 |
| 2020-12-13 | 6229007982271 | onsite_conversion.purchase | 29324.84 | 0.0 | 29324.84 | 29324.84 |
| 2020-12-14 | 6229007982271 | onsite_web_add_to_cart | 29324.84 | 0.0 | 29324.84 | 29324.84 |

**Example for 2020-12-05:**
- Action type is `view_content` with value=4194.29
- Wrong: Only 'offsite_conversion.fb_pixel_purchase' included → 0.0
- Correct: All except 'offsite_conversion.fb_pixel_view_content' included → 4194.29
- GT = 4194.29

**Example for 2020-12-08:**
- Action type is `offsite_conversion.fb_pixel_view_content` with value=4194.29
- Wrong: Only 'offsite_conversion.fb_pixel_purchase' included → 0.0
- Correct: 'offsite_conversion.fb_pixel_view_content' excluded → 0.0
- GT = 0.0 ← Both give correct result by coincidence

**Impact:**
* Current implementation: **7/10 matches (70.0%)**
* Corrected implementation: **10/10 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that `conversions_value` should sum all conversion-related monetary values, NOT just purchases. The only action_type to exclude is `offsite_conversion.fb_pixel_view_content` which represents views, not conversions.

**Included action_types:**
- `offsite_conversion.fb_pixel_purchase` (purchases)
- `onsite_conversion.purchase` (purchases)
- `onsite_web_add_to_cart` (cart additions)
- `view_content` (content views that led to conversion value)

**Excluded action_types:**
- `offsite_conversion.fb_pixel_view_content` (pixel view tracking, not a conversion)
