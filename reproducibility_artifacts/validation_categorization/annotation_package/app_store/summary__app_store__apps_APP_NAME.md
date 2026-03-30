# Column Mismatch Summary

## Database: app_store
## Table: apps
## Column: APP_NAME

### Description
Name of the app.

---

## Root Cause
**Wrong source table: Query uses only user_reviews table instead of starting from playstore (the canonical app list)**

### Incorrect SQL Logic
```sql
SELECT
    APP AS app_name,
    ...
FROM user_reviews
GROUP BY APP
```

### Correct SQL Logic
```sql
WITH playstore_apps AS (
    SELECT DISTINCT App as app_name
    FROM playstore
),
review_stats AS (
    SELECT App as app_name, ...
    FROM user_reviews
    GROUP BY App
)
SELECT
    p.app_name,
    ...
FROM playstore_apps p
LEFT JOIN review_stats r ON p.app_name = r.app_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The `apps` table should contain one record per app. The canonical list of apps comes from the `playstore` table, which represents the app store catalog.

* **What the SQL actually computes**: The incorrect SQL queries only from `user_reviews`, which means it only outputs apps that have at least one review. Apps without any reviews are completely omitted.

* **Schema semantics**:
  - `playstore` table: Contains the app catalog (9,659 unique apps) - this is the authoritative list of apps
  - `user_reviews` table: Contains user reviews for apps (only 1,074 unique apps have reviews)

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Wrong Logic | Correct Logic | Ground Truth |
| ------ | ----------- | ------------- | ------------ |
| Total apps | 1,074 | 9,659 | 9,659 |
| Apps missing | 8,639 | 0 | 0 |

**Example apps missing from incorrect query:**
- BL IP-Camera
- Stolica.bg
- ec.tv
- Chicken Invaders 3
- FP Connect
- CT Scan Cross Sectional Anatomy
- TrueMoney Wallet
- Watch Face Swiss AJ-6

These apps exist in the playstore but have no user reviews.

**Impact:**
* Current implementation: **1,020/9,659 matches (10.6%)** - missing 8,639 apps
* Corrected implementation: **9,659/9,659 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The data model specifies "Each record represents an app" - this means ALL apps from the playstore should be included, not just those with reviews. Apps without reviews should still appear in the output with appropriate NULL/0 values for their metrics.
