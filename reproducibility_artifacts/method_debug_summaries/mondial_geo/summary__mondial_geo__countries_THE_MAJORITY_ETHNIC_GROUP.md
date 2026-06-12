# Column Mismatch Summary

## Database: mondial_geo
## Table: countries
## Column: THE_MAJORITY_ETHNIC_GROUP

**Description:**
The majority ethnic group in the country, with ties broken by the ascending order of the ethnic group name.

---

## Root Cause
**SQL correctly picks the highest percentage ethnic group, but GT appears to pick a low-percentage group (inverted logic)**

### Current SQL Logic (Semantically Correct)
```sql
ethnic_groups AS (
    SELECT
        COUNTRY AS country_code,
        NAME AS ethnic_group_name,
        CAST(PERCENTAGE AS FLOAT) AS percentage,
        ROW_NUMBER() OVER (PARTITION BY COUNTRY ORDER BY CAST(PERCENTAGE AS FLOAT) DESC, NAME ASC) AS rn,
        COUNT(*) OVER (PARTITION BY COUNTRY) AS num_ethnic_groups
    FROM {{ source('airbyte_schema', 'ETHNICGROUP') }}
),

majority_ethnic_group AS (
    SELECT
        country_code,
        ethnic_group_name AS the_majority_ethnic_group,
        num_ethnic_groups
    FROM ethnic_groups
    WHERE rn = 1
)
```

### SQL Logic to Match GT (Semantically Incorrect)
```sql
ethnic_groups AS (
    SELECT
        COUNTRY AS country_code,
        NAME AS ethnic_group_name,
        CAST(PERCENTAGE AS FLOAT) AS percentage,
        ROW_NUMBER() OVER (PARTITION BY COUNTRY ORDER BY CAST(PERCENTAGE AS FLOAT) ASC, NAME ASC) AS rn,
        -- Changed: ASC instead of DESC ^^^^^^^^^^
        COUNT(*) OVER (PARTITION BY COUNTRY) AS num_ethnic_groups
    FROM {{ source('airbyte_schema', 'ETHNICGROUP') }}
)
```

---

## Why the Original Logic Is Actually Correct

* **What the column description says**: "The majority ethnic group in the country"
* **What the SQL computes**: The ethnic group with the HIGHEST percentage (true majority)
* **What the GT expects**: A low-percentage ethnic group (appears to be inverted logic)

The SQL interpretation is semantically correct - "majority ethnic group" should be the one with the highest percentage. The GT appears to have been generated with inverted sorting logic (ASC instead of DESC), resulting in minority groups being selected instead.

---

## Evidence

**Key comparison demonstrating the discrepancy:**

| Country | Ethnic Groups (sorted by % DESC) | SQL Result (Majority) | GT Result (Minority) |
| ------- | -------------------------------- | --------------------- | -------------------- |
| Afghanistan | Pashtun (38%), Tajik (25%), Hazara (19%), Uzbek (6%) | Pashtun | Uzbek |
| Bahrain | Bahraini (63%), Asian (13%), Arab (10%), Iranian (8%) | Bahraini | Iranian |
| Belize | Creole (30%), Maya (11%), Garifuna (7%) | Creole | Garifuna |
| Bolivia | Quechua (30%), Aymara (25%), European (5%) | Quechua | European |
| Ethiopia | Oromo (40%), Amhara Tigrean (32%), Sidamo (9%), ... | Oromo | Sidamo |
| Iran | Persian (51%), Azerbaijani (24%), Gilaki Mazandarani (8%), ... | Persian | Gilaki Mazandarani |

**Pattern Analysis:**
- SQL picks position 0 (highest percentage) - semantically correct for "majority"
- GT picks a low-ranked position (often near the bottom of the list)

**Impact:**
* Current implementation: **208/238 matches (87.4%)**
* If using inverted logic (ASC): Would match GT but be semantically incorrect

---

## Result

**SQL is semantically correct; GT appears to have inverted logic**

**Key insight:**
The SQL correctly implements "majority ethnic group" by selecting the ethnic group with the highest percentage of the population. The ground truth appears to have been generated with inverted sorting logic, selecting low-percentage groups instead.

For the 30 mismatched countries, the SQL's result (highest percentage group) is the correct interpretation of "majority ethnic group." The GT's result (low-percentage group) would be more accurately described as a "minority ethnic group."

**Examples of correct majority group identification by SQL:**
* Afghanistan: Pashtun (38%) - not Uzbek (6%)
* Bahrain: Bahraini (63%) - not Iranian (8%)
* Ethiopia: Oromo (40%) - not Sidamo (9%)
* Iran: Persian (51%) - not Gilaki Mazandarani (8%)
