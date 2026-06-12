# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__url_report
## Column: AD_NAME

**Description:**
The name of the corresponding ad; title_part_1 is used as the ad name as a proxy as one is not provided by the data source.

---

## Root Cause
**No semantic error: Values match 100%**

### Current SQL Logic
```sql
ad_history AS (
    SELECT
        id AS ad_id,
        title_part_1 AS ad_name
    FROM {{ source('airbyte_schema', 'ad_history') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY modified_time DESC) = 1
)

SELECT
    ...
    adh.ad_name,
    ...
FROM ad_performance ap
LEFT JOIN ad_history adh ON ap.ad_id = adh.ad_id
```

### Note on Issue
The SQL logic is semantically correct. The column values match 100%.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Name of the ad, using title_part_1 as proxy

* **What the SQL actually computes:**
  * Correctly uses title_part_1 from ad_history as ad_name
  * Value distribution matches GT exactly

**Value distribution (both GT and Predicted):**
| AD_NAME | Count |
| ------- | ----- |
| WwfGmlh/43PQDdH8bbMi9Q== | 257 |
| e7L/v/fiGh2rg37b19Quew== | 38 |
| 7Wzn6woQmbWz7u9JX7VLrQ== | 14 |
| LKxLUP62OMuqYOnH5orp0A== | 3 |

---

## Evidence

**Key comparison demonstrating the match:**

| Metric | GT | Predicted |
| ------ | -- | --------- |
| Total rows | 312 | 312 |
| Unique values | 4 | 4 |
| Distribution identical | Yes | Yes |

**Impact:**
* Current implementation: **312/312 matches (100%)**

---

## Result

**Perfect match - no semantic error**

The AD_NAME column is correctly implemented using title_part_1 as the proxy.
