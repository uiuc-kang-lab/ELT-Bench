# Column Mismatch Summary

## Database: mondial_geo
## Table: countries
## Column: HAS_OVER_1_ORGANIZATIONS_AND_AN_INFLATION_RATE_OF_OVER_3_PER

**Description:**
Set to 1 if the country has over 1 organizations and an inflation rate of over 3, otherwise, set to 0.

---

## Root Cause
**SQL uses wrong table: IS_MEMBER (organization memberships) instead of ORGANIZATION (organizations hosted by country)**

### Incorrect SQL Logic
```sql
organizations_and_inflation AS (
    SELECT
        c.CODE AS country_code,
        CASE
            WHEN COUNT(DISTINCT im.ORGANIZATION) > 1 AND MAX(e.INFLATION) > 3 THEN 1
            ELSE 0
        END AS has_over_1_organizations_and_an_inflation_rate_of_over_3_per
    FROM {{ source('airbyte_schema', 'COUNTRY') }} c
    LEFT JOIN {{ source('airbyte_schema', 'IS_MEMBER') }} im ON c.CODE = im.COUNTRY
    LEFT JOIN {{ source('airbyte_schema', 'ECONOMY') }} e ON c.CODE = e.COUNTRY
    GROUP BY c.CODE
)
```

### Correct SQL Logic
```sql
organizations_and_inflation AS (
    SELECT
        c.CODE AS country_code,
        CASE
            WHEN COUNT(o.Abbreviation) > 1 AND MAX(e.INFLATION) > 3 THEN 1
            ELSE 0
        END AS has_over_1_organizations_and_an_inflation_rate_of_over_3_per
    FROM {{ source('airbyte_schema', 'COUNTRY') }} c
    LEFT JOIN {{ source('airbyte_schema', 'ORGANIZATION') }} o ON c.CODE = o.COUNTRY
    LEFT JOIN {{ source('airbyte_schema', 'ECONOMY') }} e ON c.CODE = e.COUNTRY
    GROUP BY c.CODE
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: "the country has over 1 organizations" refers to organizations that the country **hosts** (i.e., where the organization's headquarters are located)
* **What the SQL computes**: Counts organizations that the country is a **member** of

The key difference between the two tables:
- **IS_MEMBER**: Lists which organizations a country is a member of (e.g., USA is a member of UN, NATO, OECD, etc.) - most countries are members of dozens of organizations
- **ORGANIZATION**: Lists where organization headquarters are located (e.g., UN is headquartered in USA, EU headquarters in Belgium) - only a few countries host multiple organizations

---

## Evidence

**Key comparison demonstrating the error:**

| Country | IS_MEMBER count (memberships) | ORGANIZATION count (hosted) | Inflation | Wrong Flag | Correct Flag | Ground Truth |
| ------- | ----------------------------- | --------------------------- | --------- | ---------- | ------------ | ------------ |
| United States | 72 | 21 | 2.5% | 0 | 0 | 0 |
| France | 83 | 10 | 1.2% | 0 | 0 | 0 |
| United Kingdom | 74 | 4 | 3.1% | 1 | 1 | 1 |
| Saudi Arabia | 64 | 3 | 5.0% | 1 | 1 | 1 |
| Albania | 37 | 0 | 16.0% | 1 | 0 | 0 |
| Angola | 19 | 0 | 31.0% | 1 | 0 | 0 |

**Organizations hosted by country (from ORGANIZATION table):**
- USA: 21 organizations
- Switzerland: 18 organizations
- France: 10 organizations
- Belgium: 10 organizations
- Austria: 6 organizations
- United Kingdom: 4 organizations
- Saudi Arabia: 3 organizations
- Cote dIvoire, Ethiopia, Indonesia, Italy, Jordan: 2 organizations each

**Impact:**
* Current implementation: **92/238 matches (38.7%)**
* Corrected implementation: **238/238 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Countries where `HAS_OVER_1_ORGANIZATIONS_AND_AN_INFLATION_RATE_OF_OVER_3_PER = 1`:**

Only 6 countries host more than 1 organization AND have inflation > 3%:
* **Cote dIvoire** (hosts 2 orgs: AfDB, Entente; inflation: 10.0%)
* **Ethiopia** (hosts 2 orgs: ECA, OAU; inflation: 10.0%)
* **Indonesia** (hosts 2 orgs: ASEAN, NAM; inflation: 8.6%)
* **Italy** (hosts 2 orgs: FAO, IFAD; inflation: 5.4%)
* **Saudi Arabia** (hosts 3 orgs: GCC, IDB, OIC; inflation: 5.0%)
* **United Kingdom** (hosts 4 orgs: EBRD, IMO, Inmarsat, C; inflation: 3.1%)
