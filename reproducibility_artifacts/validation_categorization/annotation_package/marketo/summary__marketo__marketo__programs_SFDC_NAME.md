# Column Mismatch Summary

## Database: marketo
## Table: marketo__programs
## Column: SFDC_NAME

**Description:**
Name of the linked SFDC campaign if applicable.

---

## Root Cause
**JSON encoding issue: Values are wrapped in escaped JSON string format instead of plain text**

### Incorrect SQL Logic
```sql
SELECT
    ...
    p.sfdc_name,  -- Returns JSON-encoded values: """null""", "\"b18e32bae70c5bd75ce67816b087b40c\""
    ...
FROM programs p
```

### Correct SQL Logic
```sql
SELECT
    ...
    CASE
        WHEN p.sfdc_name IS NULL OR p.sfdc_name = 'null' THEN NULL
        ELSE PARSE_JSON(p.sfdc_name)::STRING
    END AS sfdc_name,  -- Returns plain values: NULL, 'b18e32bae70c5bd75ce67816b087b40c'
    ...
FROM programs p
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * SFDC Name is the Salesforce Campaign name (appears to be hashed in this dataset)
  * NULL when program is not linked to Salesforce
  * GT has empty/NULL for missing values, plain strings for actual names

* **What the SQL actually computes:**
  * Returns JSON-encoded strings with escaped quotes
  * NULL becomes `"""null"""`
  * Actual names become `"\"b18e32bae70c5bd75ce67816b087b40c\""`
  * Values are double-escaped when output to CSV

---

## Evidence

**Key comparison demonstrating the error:**

| PROGRAM_ID | GT SFDC_NAME | Predicted SFDC_NAME |
| ---------- | ------------ | ------------------- |
| 1001 | (NULL/empty) | """null""" |
| 1040 | b18e32bae70c5bd75ce67816b087b40c | "\"b18e32bae70c5bd75ce67816b087b40c\"" |
| 1043 | 392f12c3e37fc1674258e2470d1afd7c | "\"392f12c3e37fc1674258e2470d1afd7c\"" |
| 1102 | f8c3381624edb09926c31316c1ac9797 | "\"f8c3381624edb09926c31316c1ac9797\"" |

**Impact:**
* Current implementation: **0/100 matches (0%)**
* Corrected implementation: **100/100 matches (100%)**

---

## Result

**Zero matches - JSON encoding not properly handled**

The fix requires parsing the JSON-encoded values from the source data. Same root cause as PROGRAM_STATUS and SFDC_ID - the source data contains JSON-encoded strings that need to be properly extracted using appropriate JSON parsing functions.
