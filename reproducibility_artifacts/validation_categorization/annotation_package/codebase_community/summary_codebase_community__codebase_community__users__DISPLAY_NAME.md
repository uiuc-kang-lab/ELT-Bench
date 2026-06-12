# SQL Column Debugging Summary

## Database: codebase_community
## Table: codebase_community__users
## Column: DISPLAY_NAME

**Description:**
Display name of the user.

---

## Root Cause
**Whitespace trimming issue - SQL or export process strips leading/trailing whitespace that exists in the source data and ground truth.**

### Current SQL Logic
```sql
users_base AS (
    SELECT
        DISPLAYNAME AS display_name,
        ...
    FROM users
)
```

### Correct SQL Logic (to preserve whitespace)
```sql
users_base AS (
    SELECT
        DISPLAYNAME AS display_name,  -- Ensure no implicit TRIM is applied
        ...
    FROM users
)
```

---

## Why the Original Logic Has Issues

* **What the column description means:** The display name of the user, exactly as stored in the source data.

* **What the SQL actually computes:** The SQL correctly selects `DISPLAYNAME AS display_name`, but whitespace is being trimmed either:
  1. During data loading (implicit TRIM in database)
  2. During CSV export
  3. As part of the SQL execution environment's default behavior

**Source data contains whitespace:**
- 27 display names have trailing whitespace
- 1 display name has leading whitespace (`'   Raid-Mahbouba'`)
- Ground truth preserves this whitespace
- Predicted output has whitespace stripped

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Value |
| ------ | ----- |
| Total users | 40,325 |
| Exact matches | 40,297 |
| Mismatches | 28 |
| Match rate | 99.93% |

**Sample mismatches (whitespace differences):**

| User ID | GT Value | Pred Value | Issue |
|---------|----------|------------|-------|
| 1701 | `'Mithun P '` | `'Mithun P'` | Trailing space |
| 1906 | `'Alos '` | `'Alos'` | Trailing space |
| 21275 | `'   Raid-Mahbouba'` | `'Raid-Mahbouba'` | Leading spaces |
| 22027 | `'Alex '` | `'Alex'` | Trailing space |
| 26938 | `'Alan '` | `'Alan'` | Trailing space |
| 27234 | `'Trevor '` | `'Trevor'` | Trailing space |
| 27812 | `'Rob '` | `'Rob'` | Trailing space |
| 28227 | `'emmet '` | `'emmet'` | Trailing space |

**Whitespace analysis from source:**
- Source DisplayName values with trailing whitespace: 27
- Source DisplayName values with leading whitespace: 1
- GT matches Source exactly: 40,325/40,325 (100%)

**Impact:**
* Current implementation: **40,297/40,325 matches (99.93%)**
* With whitespace preserved: **40,325/40,325 matches (100%)**

---

## Result

**Near-perfect match - whitespace handling issue**

The SQL logic itself is correct (`DISPLAYNAME AS display_name`). The 28 mismatches are due to whitespace being trimmed during data processing or export, not a SQL logic error.

**Users affected (28 total):**
- 27 users with trailing whitespace in their display names
- 1 user with leading whitespace (`Raid-Mahbouba` with 3 leading spaces)

This is a data formatting/export issue rather than a fundamental SQL logic error.
