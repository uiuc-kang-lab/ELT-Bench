# Column Mismatch Summary

## Database: superstore
## Table: products
## Column: PRODUCT_NAME

**Description:**
The name of the product.

---

## Root Cause
**Product ID to Name mapping inconsistency: Same Product_ID maps to different Product_Names in GT vs source**

### Incorrect SQL Logic
```sql
product AS (
    SELECT
        Product_ID,
        Product_Name
    FROM (
        SELECT DISTINCT
            Product_ID,
            Product_Name,
            ROW_NUMBER() OVER (PARTITION BY Product_ID ORDER BY Product_Name) AS rn
        FROM {{ source('airbyte_schema', 'product') }}
    )
    WHERE rn = 1
)
```

### Analysis
The SQL uses `ORDER BY Product_Name` to break ties when a Product_ID has multiple names, selecting the first alphabetically. However, GT may use a different selection criteria or have different source data.

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The name of the product associated with the product ID

* **What the SQL actually computes:**
  * When a Product_ID has multiple names in the source, it picks the first alphabetically
  * GT may expect a different name for the same Product_ID

---

## Evidence

**Key comparison demonstrating the error:**

| Product_ID | GT Name | Pred Name |
| ---------- | ------- | --------- |
| FUR-BO-10002213 | Sauder Forest Hills Library, Woodland Oak Finish | DMI Eclipse Executive Suite Bookcases |
| FUR-FU-10004017 | Tenex Contemporary Contur Chairmats... | Executive Impressions 13" Chairman Wall Clock |
| FUR-FU-10004091 | Howard Miller 13" Diameter Goldtone Round Wall Clock | Eldon 200 Class Desk Accessories, Black |

**Impact:**
* Current implementation: **1859/1888 matches (98.46%)**
* 29 products have mismatched names

---

## Result

**Near-perfect match with minor data inconsistencies**

The mismatch appears to be due to data quality issues where the same Product_ID has different associated names in different data sources.
