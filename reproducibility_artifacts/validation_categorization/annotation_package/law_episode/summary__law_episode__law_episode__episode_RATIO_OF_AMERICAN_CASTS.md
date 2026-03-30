# Column Mismatch Summary

## Database: law_episode
## Table: law_episode__episode
## Column: RATIO_OF_AMERICAN_CASTS

### Description
the ratio of American casts in the episode

---

## Root Cause
**Two issues: (1) Output format - decimal instead of percentage, and (2) Incorrect denominator calculation**

### Incorrect SQL Logic
```sql
american_cast_ratio AS (
    SELECT
        c.EPISODE_ID,
        COUNT(CASE WHEN p.BIRTH_COUNTRY = 'USA' THEN 1 END)::FLOAT / NULLIF(COUNT(*), 0) AS ratio_of_American_casts
    FROM {{ source('airbyte_schema', 'CREDIT') }} c
    LEFT JOIN {{ source('airbyte_schema', 'PERSON') }} p ON c.PERSON_ID = p.PERSON_ID
    WHERE c.CATEGORY = 'Cast'
    GROUP BY c.EPISODE_ID
)
```

### Correct SQL Logic
```sql
american_cast_ratio AS (
    SELECT
        c.EPISODE_ID,
        COUNT(CASE WHEN p.BIRTH_COUNTRY = 'USA' THEN 1 END)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS ratio_of_American_casts
    FROM {{ source('airbyte_schema', 'CREDIT') }} c
    LEFT JOIN {{ source('airbyte_schema', 'PERSON') }} p ON c.PERSON_ID = p.PERSON_ID
    WHERE c.CATEGORY = 'Cast'
    -- Note: Additional filtering or different denominator logic may be required
    -- based on specific business rules (e.g., excluding unknown nationalities)
    GROUP BY c.EPISODE_ID
)
```

---

## Why the Original Logic Is Wrong

The current implementation has two primary issues:

1. **Format Issue**: The SQL returns a decimal (e.g., 0.71) but the ground truth expects a percentage (e.g., 79.41). The calculation needs to multiply by 100.

2. **Denominator Issue**: The ground truth uses a different subset of cast members as the denominator. The implied denominators from reverse-engineering don't match simple counts of total cast or credited cast.

**What the column description means:**
- "the ratio of American casts in the episode" = percentage of cast members born in USA

**What the SQL actually computes:**
- Ratio as a decimal (0-1) of USA-born cast / all cast members

**Schema semantics from `source_schemas`:**
- `Credit.category = 'Cast'`: Identifies cast member records
- `Person.birth_country`: Country where person was born (can be NULL for unknown)
- `Credit.credited`: Whether the credit appeared in episode credits (1 or 0)

---

## Evidence

**Key comparison demonstrating the format difference:**

| Episode | GT (percentage) | Predicted (decimal) | GT as decimal | Calc as % |
| ------- | --------------- | ------------------- | ------------- | --------- |
| tt0629146 | 79.41 | 0.7105 | 0.7941 | 71.05 |
| tt0629149 | 76.00 | 0.5135 | 0.7600 | 51.35 |
| tt0629153 | 83.33 | 0.6944 | 0.8333 | 69.44 |
| tt0629248 | 72.22 | 0.4194 | 0.7222 | 41.94 |

**Denominator analysis for tt0629146 ("Admissions"):**
- Total cast: 38
- USA cast: 27
- Credited cast (credited=1): 37
- Cast with known birth_country: 27 (all USA)
- Ground truth ratio: 79.41% = 27/34
- Implied denominator: 34

The implied denominator (34) doesn't match:
- Total cast (38)
- Credited cast (37)
- Known country cast (27)

This suggests a specific business rule for the denominator that isn't immediately apparent from the schema.

**Impact:**
* Current implementation: **0/24 matches (0%)**
* With percentage format: **Still 0/24 matches** (denominator issue remains)

---

## Result
⚠️ **Partial resolution - format issue identified but denominator logic unclear**

**Known issues:**
1. Output should be percentage (multiply by 100)
2. Denominator calculation uses a specific subset of cast members

**Possible denominator interpretations tested:**
- All cast: No match
- Credited cast only: No match
- Cast with known birth_country: No match
- Distinct persons: No match

**Investigation notes:**
The ground truth appears to use a denominator that varies by episode in a pattern that doesn't correspond to simple filtering criteria. Further investigation with business stakeholders or additional documentation may be needed to determine the exact calculation logic.
