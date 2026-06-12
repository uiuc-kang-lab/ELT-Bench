# Column Mismatch Summary

## Database: address
## Table: states
## Column: GREATER_THAN_50_CBSA_METRO

### Description
Set to 1 if the state has greater than 50 CBSA officers of metro type, otherwise, set to 0.

---

## Root Cause
**Semantic misinterpretation: Used COUNT(DISTINCT CBSA) instead of COUNT(*) - counting unique metro areas instead of total metro-linked zip codes**

### Incorrect SQL Logic
```sql
cbsa_metro_count AS (
    SELECT
        z.state,
        COUNT(DISTINCT c.CBSA) AS cbsa_metro_count
    FROM cbsa c
    INNER JOIN zip_data z ON c.CBSA = z.CBSA
    WHERE UPPER(c.CBSA_type) = 'METRO'
    GROUP BY z.state
)
-- Set to 1 if cbsa_metro_count > 50
```

### Correct SQL Logic
```sql
cbsa_metro_count AS (
    SELECT
        z.state,
        COUNT(*) AS cbsa_metro_count
    FROM cbsa c
    INNER JOIN zip_data z ON c.CBSA = z.CBSA
    WHERE UPPER(c.CBSA_type) = 'METRO'
    GROUP BY z.state
)
-- Set to 1 if cbsa_metro_count > 50
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: The description says "greater than 50 CBSA officers of metro type." The term "officers" in the schema context refers to the CBSA records/entries associated with zip codes (as indicated by `source_schemas/CBSA.csv` which describes CBSA as "the code of the cbsa officer").

* **What the SQL actually computes**: The incorrect SQL counts the number of *unique* CBSA codes (metro areas) that have at least one zip code in the state. Since there are only 209 metro CBSAs total nationwide, no state can have more than 50 distinct metro CBSAs - Florida has the most with only 22.

* **Schema semantics**: The `zip_data` table has a CBSA column linking each zip code to a CBSA. "CBSA officers" means the count of zip codes that are linked to metro-type CBSAs, not the count of unique metro areas.

---

## Evidence
**Key comparison demonstrating the error:**

| Metric | Wrong Logic (DISTINCT) | Correct Logic (COUNT) |
| ------ | ---------------------- | --------------------- |
| Max count for any state | 22 (Florida) | 1,549 (New York) |
| States with count > 50 | 0 | 25 |

**State counts comparison:**

| State | COUNT DISTINCT | COUNT(*) | GT Value |
| ----- | -------------- | -------- | -------- |
| NY    | 13             | 1,549    | 1        |
| PA    | 20             | 1,519    | 1        |
| FL    | 22             | 1,345    | 1        |
| OH    | 14             | 864      | 1        |
| VA    | 11             | 815      | 1        |
| RI    | 4              | 90       | 1        |
| DE    | 2              | 96       | 1        |
| AK    | 0              | 0        | 0        |

**Impact:**
* Current implementation: **37/62 matches (59.7%)** - predicts 0 for all states
* Corrected implementation: **62/62 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**States where `GREATER_THAN_50_CBSA_METRO = 1` (metro zip count > 50):**
* NY (1,549), PA (1,519), FL (1,345), OH (864), VA (815)
* NJ (722), NC (692), MA (671), MI (658), GA (609)
* IN (571), MD (543), AL (514), TN (483), WV (426)
* SC (383), CT (381), KY (322), DC (270), ME (174)
* PR (168), MS (168), NH (102), DE (96), RI (90)
