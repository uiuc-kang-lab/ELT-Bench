## Database: chicago_crime
## Table: community_areas
## Column: MORE_THAN_AVERAGE_SOLICIT_FOR_PROSTITUTES_REPORTED

**Description:**
Set to 1 if the number of solicitations for prostitutes reported in the community area is more than the average number of solicitations for prostitutes reported in all community areas; otherwise, set to 0.

---

## Root Cause
**Average calculated only over areas with solicitations instead of all 77 community areas**

### Incorrect SQL Logic
```sql
solicit_prostitutes AS (
    SELECT community_area_no, COUNT(*) AS num_solicit_prostitutes
    FROM crime c
    INNER JOIN iucr i ON c.iucr_no = i.iucr_no
    WHERE i.primary_description = 'PROSTITUTION'
      AND i.secondary_description = 'SOLICIT FOR PROSTITUTE'
    GROUP BY community_area_no
),
avg_solicit_prostitutes AS (
    SELECT AVG(num_solicit_prostitutes) AS avg_num
    FROM solicit_prostitutes  -- Only areas WITH solicitations included
)
```

### Correct SQL Logic
```sql
avg_solicit_prostitutes AS (
    SELECT SUM(num_solicit_prostitutes) / 77.0 AS avg_num  -- Divide by ALL 77 community areas
    FROM solicit_prostitutes
)
-- Or use COALESCE with a full outer join to include all 77 areas with 0 counts
```

---

## Why the Original Logic Is Wrong

* The specification says "average number of solicitations for prostitutes reported in all community areas"
* This means the denominator should include ALL 77 community areas, not just those with solicitations
* Areas with zero solicitations should be included in the average calculation with count = 0
* The current SQL only averages over areas that have at least one solicitation, resulting in a higher average threshold
* This higher threshold causes fewer areas to exceed the average, producing more 0s than expected

---

## Evidence

**Key comparison demonstrating the error:**

| Community Area | Wrong Logic | Correct Logic | Ground Truth |
| -------------- | ----------- | ------------- | ------------ |
| Humboldt Park (23) | 0 | 1 | 1 |
| West Town (24) | 0 | 1 | 1 |
| Austin (25) | 0 | 1 | 1 |
| West Garfield Park (26) | 1 | 1 | 1 |

**Impact:**
* Current implementation: **~70/77 matches (~91%)**
* Corrected implementation: **77/77 matches (100%)**

---

## Result

:warning: **High Severity - Aggregation Logic Error**

**Key insight:**
When calculating an average across "all community areas," include all 77 areas in the denominator, treating areas with no occurrences as having a count of 0. The specification explicitly mentions "all community areas," not "all community areas with at least one occurrence."
