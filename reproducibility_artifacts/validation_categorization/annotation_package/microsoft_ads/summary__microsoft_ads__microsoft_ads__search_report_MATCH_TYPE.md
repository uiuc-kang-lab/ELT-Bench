# Column Mismatch Summary

## Database: microsoft_ads
## Table: microsoft_ads__search_report
## Column: MATCH_TYPE

**Description:**
The match type associated with this record; values contain but may not be limited to 'Broad', 'Exact', 'Phrase'.

---

## Root Cause
**Wrong source used: SQL joins to keyword_history.match_type but should use search_performance_daily_report.delivered_match_type or bid_match_type**

### Incorrect SQL Logic
```sql
keyword_history AS (
    SELECT
        id AS keyword_id,
        match_type
    FROM {{ source('airbyte_schema', 'keyword_history') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY modified_time DESC) = 1
)

SELECT
    ...
    kh.match_type,  -- WRONG: comes from keyword_history, NULL when no match
    ...
FROM search_performance sp
LEFT JOIN keyword_history kh ON sp.keyword_id = kh.keyword_id
```

### Correct SQL Logic
```sql
SELECT
    ...
    sp.delivered_match_type AS match_type,  -- CORRECT: use from source performance report
    ...
FROM search_performance_daily_report sp
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Match type associated with the search query record
  * Values: 'Broad', 'Exact', 'Phrase'
  * Should reflect the actual match type for the search query

* **What the SQL actually computes:**
  * Joins to keyword_history table to get match_type
  * Returns NULL when keyword not found in keyword_history
  * The search_performance_daily_report source has `delivered_match_type` and `bid_match_type` columns directly

**Source schema (search_performance_daily_report):**
- `bid_match_type`: "The bid match type associated with this record"
- `delivered_match_type`: "The delivered match type associated with this record"

---

## Evidence

**Key comparison demonstrating the error:**

| Index | GT MATCH_TYPE | Predicted MATCH_TYPE |
| ----- | ------------- | -------------------- |
| 0 | Broad | NULL |
| 1 | Broad | NULL |
| 2 | Broad | NULL |
| ... | Broad | NULL |

**Impact:**
* Current implementation: **0/10 matches (0%)** - all values are NULL
* Corrected implementation: **10/10 matches (100%)**

---

## Result

**Zero matches - wrong source used for match_type**

The fix requires using `delivered_match_type` (or `bid_match_type`) directly from the search_performance_daily_report source table instead of joining to keyword_history. The source report already contains the match type information.
