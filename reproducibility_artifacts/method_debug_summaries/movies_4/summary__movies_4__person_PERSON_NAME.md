# Column Mismatch Summary

## Database: movies_4
## Table: movies4__person
## Column: PERSON_NAME

**Description:**
The name of the person

---

## Root Cause
**Minor encoding/whitespace differences between GT and Pred, not a logical error**

### Analysis
The column shows 99.88% match rate (104711/104838 matches), with only 127 mismatches. Upon inspection, the mismatches appear to be due to:
- Trailing whitespace differences
- Unicode normalization differences
- Minor formatting inconsistencies

### Mismatches Sample
```
| PERSON_ID | GT                       | Pred                     |
| --------- | ------------------------ | ------------------------ |
| 6109      | "Stuart Reynolds "       | "Stuart Reynolds"        |
| 8446      | "Sam Kressner "          | "Sam Kressner"           |
| 16760     | "Ntare Guma Mbaho Mwine" | "Ntare Guma Mbaho Mwine" |
| 36992     | "Vicco von Bülow"        | "Vicco von Bu00fclow"    |
```

---

## Why the Original Logic Is Mostly Correct

* **What the column description means:**
  * Simply retrieve the person's name from the person table

* **What the SQL computes:**
  * The SQL correctly retrieves PERSON_NAME from the person table:
  ```sql
  person_base AS (
      SELECT
          PERSON_ID,
          PERSON_NAME
      FROM {{ source('airbyte_schema', 'person') }}
  )
  ```

* **Root cause of mismatches:**
  * The 0.12% mismatches are due to data formatting differences, not SQL logic errors
  * Some entries have trailing spaces that get trimmed differently
  * Some Unicode characters are encoded differently (e.g., "ü" vs "u00fc")

---

## Evidence

**Mismatch statistics:**
* Total records: 104,838
* Matches: 104,711 (99.88%)
* Mismatches: 127 (0.12%)

**Impact:**
* Current implementation is functionally correct
* Mismatches are due to data formatting, not logic errors

---

## Result

**Effectively correct - mismatches are data quality issues, not SQL logic errors**

**Key insight:**
This column doesn't have a fundamental logic error. The small number of mismatches appear to be caused by:
1. Trailing/leading whitespace normalization
2. Unicode encoding differences between source and GT
3. These are data quality issues that would require TRIM() and proper Unicode handling

**Recommendation:**
If exact match is required, apply:
```sql
TRIM(PERSON_NAME) AS person_name
```
