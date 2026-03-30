# Column Mismatch Summary

## Database: shakespeare
## Table: shakespeare__works
## Column: NUM_CHARACTERS

### Description
The number of characters in the work, replace NULL values with 0.

---

## Root Cause
**Aggregation error: SQL sums distinct characters per chapter instead of counting distinct characters per work**

### Incorrect SQL Logic
```sql
character_counts AS (
    SELECT
        p.chapter_id,
        COUNT(DISTINCT p.character_id) as num_characters_in_chapter
    FROM {{ source('airbyte_schema', 'paragraphs') }} p
    GROUP BY p.chapter_id
),

work_character_counts AS (
    SELECT
        ch.work_id,
        SUM(cc.num_characters_in_chapter) as total_characters
    FROM {{ source('airbyte_schema', 'chapters') }} ch
    LEFT JOIN character_counts cc ON ch.id = cc.chapter_id
    GROUP BY ch.work_id
)
```

### Correct SQL Logic
```sql
work_character_counts AS (
    SELECT
        ch.work_id,
        COUNT(DISTINCT p.character_id) as total_characters
    FROM {{ source('airbyte_schema', 'chapters') }} ch
    LEFT JOIN {{ source('airbyte_schema', 'paragraphs') }} p ON ch.id = p.chapter_id
    GROUP BY ch.work_id
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means**: Count the total number of unique characters that appear anywhere in the work
* **What the SQL actually computes**: Sums up the distinct character counts from each chapter, which double-counts characters that appear in multiple chapters

The current logic first counts distinct characters per chapter, then sums those counts. If a character (e.g., Hamlet) appears in multiple chapters, they get counted once per chapter instead of once per work.

**Example - "Twelfth Night":**
- The character "Viola" appears in chapters belonging to Acts 1, 2, 3, and 5
- Wrong logic: Counts Viola 4 times (once per act she appears in)
- Correct logic: Counts Viola 1 time (she is 1 character in the work)

---

## Evidence

**Key comparison demonstrating the error:**

| Work | Title | Wrong Logic (SUM per chapter) | Correct Logic (DISTINCT per work) | Ground Truth |
| ---- | ----- | ----------------------------- | --------------------------------- | ------------ |
| 1 | Twelfth Night | 98 | 19 | 19 |
| 2 | All's Well That Ends Well | 121 | 25 | 25 |
| 3 | Antony and Cleopatra | 232 | 55 | 55 |
| 4 | As You Like It | 110 | 27 | 27 |
| 5 | Comedy of Errors | 70 | 20 | 20 |
| 6 | Coriolanus | 201 | 58 | 58 |
| 8 | Hamlet | 127 | 32 | 32 |

**Impact:**
* Current implementation: **2/43 matches (4.7%)**
* Corrected implementation: **43/43 matches (100%)**

---

## Result
✅ **Perfect match with corrected logic**

**Key insight:**
The correction requires removing the intermediate aggregation step and directly counting distinct character_ids at the work level. The two-step aggregation (count per chapter, then sum) inherently overcounts characters that appear in multiple chapters.
