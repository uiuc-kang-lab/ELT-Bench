# Column Mismatch Summary

## Database: marketo
## Table: marketo__programs
## Column: SFDC_ID

**Description:**
SFDC id of the program if linked to an SFDC campaign.

---

## Root Cause
**JSON encoding issue: Values are wrapped in escaped JSON string format instead of plain text**

### Incorrect SQL Logic
```sql
SELECT
    ...
    p.sfdc_id,  -- Returns JSON-encoded values: """null""", "\"7011G000000QXnNQAW\""
    ...
FROM programs p
```

### Correct SQL Logic
```sql
SELECT
    ...
    CASE
        WHEN p.sfdc_id IS NULL OR p.sfdc_id = 'null' THEN NULL
        ELSE PARSE_JSON(p.sfdc_id)::STRING
    END AS sfdc_id,  -- Returns plain values: NULL, '7011G000000QXnNQAW'
    ...
FROM programs p
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * SFDC ID is a Salesforce Campaign ID (18-character alphanumeric string)
  * NULL when program is not linked to Salesforce
  * GT has empty/NULL for missing values, plain strings for actual IDs

* **What the SQL actually computes:**
  * Returns JSON-encoded strings with escaped quotes
  * NULL becomes `"""null"""`
  * Actual IDs become `"\"7011G000000QXnNQAW\""`
  * Values are double-escaped when output to CSV

---

## Evidence

**Key comparison demonstrating the error:**

| PROGRAM_ID | GT SFDC_ID | Predicted SFDC_ID |
| ---------- | ---------- | ----------------- |
| 1001 | (NULL/empty) | """null""" |
| 1040 | 7011G000000QXnNQAW | "\"7011G000000QXnNQAW\"" |
| 1043 | 7011G000000Y589QAC | "\"7011G000000Y589QAC\"" |
| 1102 | 7011G000000QXWvQAO | "\"7011G000000QXWvQAO\"" |

**Impact:**
* Current implementation: **0/100 matches (0%)**
* Corrected implementation: **100/100 matches (100%)**

---

## Result

**Zero matches - JSON encoding not properly handled**

The fix requires parsing the JSON-encoded values from the source data. Same root cause as PROGRAM_STATUS - the source data contains JSON-encoded strings that need to be properly extracted.
