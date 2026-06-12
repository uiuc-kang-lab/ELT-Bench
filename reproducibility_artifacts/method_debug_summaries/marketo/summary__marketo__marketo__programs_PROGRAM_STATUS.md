# Column Mismatch Summary

## Database: marketo
## Table: marketo__programs
## Column: PROGRAM_STATUS

**Description:**
Status of the program. Only valid for Email and engagement program types. Allowed values: locked, unlocked, on, off

---

## Root Cause
**JSON encoding issue: Values are wrapped in escaped JSON string format instead of plain text**

### Incorrect SQL Logic
```sql
SELECT
    ...
    p.program_status,  -- Returns JSON-encoded values: """null""", "\"completed\""
    ...
FROM programs p
```

### Correct SQL Logic
```sql
SELECT
    ...
    CASE
        WHEN p.program_status IS NULL THEN NULL
        ELSE PARSE_JSON(p.program_status)::STRING
    END AS program_status,  -- Returns plain values: NULL, 'completed'
    ...
FROM programs p
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * Plain string values: NULL, 'completed', 'unlocked', 'on', 'off'
  * GT has empty/NULL for missing values

* **What the SQL actually computes:**
  * Returns JSON-encoded strings with escaped quotes
  * NULL becomes `"""null"""`
  * 'completed' becomes `"\"completed\""`
  * Values are double-escaped when output to CSV

**Escaping issue:**
- Source data appears to have JSON-encoded values
- SQL passes them through without parsing
- CSV output adds additional escaping

---

## Evidence

**Key comparison demonstrating the error:**

| PROGRAM_ID | GT PROGRAM_STATUS | Predicted PROGRAM_STATUS |
| ---------- | ----------------- | ------------------------ |
| 1001 | (NULL/empty) | """null""" |
| 1003 | (NULL/empty) | """null""" |
| 1051 | completed | "\"completed\"" |
| 1054 | unlocked | "\"unlocked\"" |

**Impact:**
* Current implementation: **0/100 matches (0%)**
* Corrected implementation: **100/100 matches (100%)**

---

## Result

**Zero matches - JSON encoding not properly handled**

The fix requires parsing the JSON-encoded values from the source data to extract the plain string values. This is likely an issue with how the source data is stored or how the ETL pipeline handles JSON/VARIANT data types.
