# Column Mismatch Summary

## Database: legislator
## Table: current_legislators
## Column: FULL_NAME

**Description:**
The full name of the legislator.

---

## Root Cause
**Wrong source column: SQL uses `official_full_name` (which includes middle names/initials) instead of simple `first_name || ' ' || last_name`**

### Incorrect SQL Logic
```sql
COALESCE(OFFICIAL_FULL_NAME, FIRST_NAME || ' ' || COALESCE(MIDDLE_NAME || ' ', '') || LAST_NAME) AS full_name
```

### Correct SQL Logic
```sql
FIRST_NAME || ' ' || LAST_NAME AS full_name
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * The full name should be the simple combination of first name and last name
  * Ground truth consistently uses first name + space + last name format

* **What the SQL actually computes:**
  * Uses `official_full_name` as the primary source
  * Falls back to first + middle + last name concatenation
  * The `official_full_name` column includes middle names or initials (e.g., "Robert B. Aderholt")
  * Ground truth expects simple first + last name format (e.g., "Robert Aderholt")

**Name construction test results:**
| Method | Match Rate |
| ------ | ---------- |
| Official or First+Middle+Last (current) | 326/541 (60.3%) |
| First+Last only | 541/541 (100.0%) |
| Official only | 326/541 (60.3%) |
| First+Middle+Last always | 326/541 (60.3%) |

---

## Evidence

**Key comparison demonstrating the error:**

| BIOGUIDE_ID | GT (First+Last) | Predicted (Official) | first_name | middle_name | last_name |
| ----------- | --------------- | -------------------- | ---------- | ----------- | --------- |
| A000055 | Robert Aderholt | Robert B. Aderholt | Robert | B. | Aderholt |
| A000370 | Alma Adams | Alma S. Adams | Alma | S. | Adams |
| A000372 | Rick Allen | Richard W. Allen | Richard | W. | Allen |
| B000490 | Sanford Bishop | Sanford D. Bishop | Sanford | D. | Bishop |
| B001135 | Richard Burr | Richard M. Burr | Richard | M. | Burr |

**Pattern in mismatches:**
- All 215 mismatches follow the same pattern
- GT has simple "FirstName LastName" format
- Predicted includes middle name/initial from official_full_name
- official_full_name is never NULL in the source data

**Impact:**
* Current implementation: **326/541 matches (60.3%)**
* Corrected implementation: **541/541 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that the ground truth defines "full name" as the simple concatenation of first name and last name, without middle names or initials. The `official_full_name` column contains formal names with middle initials which don't match the expected output.

**Correction required:**
- Remove COALESCE with official_full_name
- Use simple: `first_name || ' ' || last_name`
