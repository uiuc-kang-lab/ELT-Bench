# SQL Column Debugging Summary

## Database: card_games
## Table: card_games__sets
## Column: HAS_JAPANESE_TRANSLATION_AND_ONLY_AVAILABLE_IN_NON_FOIL

**Description:**
Set to 1 if the card set has Japanese translation and is only available non-foil.

---

## Root Cause
**Data type mismatch: SQL compares `isNonFoilOnly = 'true'` (string) but the column contains integers (0 or 1)**

### Incorrect SQL Logic
```sql
CASE
    WHEN tps.has_japanese = 1 AND cs.isNonFoilOnly = 'true' THEN 1
    ELSE 0
END AS has_Japanese_translation_and_only_available_in_non_foil
```

### Correct SQL Logic
```sql
CASE
    WHEN tps.has_japanese = 1 AND cs.isNonFoilOnly = 1 THEN 1
    ELSE 0
END AS has_Japanese_translation_and_only_available_in_non_foil
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** Flag sets that have BOTH:
  1. A Japanese translation (exists in `set_translations` table with `language = 'Japanese'`)
  2. Only available in non-foil format (`isNonFoilOnly = TRUE/1` in `card_sets` table)

* **What the SQL actually computes:** The SQL correctly identifies sets with Japanese translations, but the `isNonFoilOnly` comparison fails because:
  - SQL compares: `cs.isNonFoilOnly = 'true'` (string literal)
  - Actual data type: `isNonFoilOnly` is INTEGER with values `0` or `1`
  - Result: The comparison `1 = 'true'` always returns FALSE in SQL

**Source table schema (from source_schemas/card_sets.csv):**
- `isNonFoilOnly`: "If the set is only available in non-foil."

**Actual data values:**
```
isNonFoilOnly value counts:
0    445 sets
1    106 sets
dtype: int64
```

The column is stored as integers, not strings like `'true'`/`'false'`.

---

## Evidence

**Key comparison demonstrating the error:**

| Metric | Value |
| ------ | ----- |
| Total sets | 551 |
| GT with flag=1 | 14 |
| Pred with flag=1 | 0 |
| Positional match | 537/551 (97.5%) |
| Semantic match (by ID) | 537/551 (97.5%) |

**Mismatch breakdown:**
- False Negatives (GT=1, Pred=0): 14 sets
- False Positives (GT=0, Pred=1): 0 sets

**All 14 false negatives (should have flag=1):**

| ID | Name | SetCode | NUM_TRANSLATIONS | isNonFoilOnly | GT | Pred |
|----|------|---------|------------------|---------------|-----|------|
| 160 | Homelands | HML | 10 | 1 | 1 | 0 |
| 166 | Ice Age | ICE | 10 | 1 | 1 | 0 |
| 25 | Archenemy | ARC | 10 | 1 | 1 | 0 |
| 297 | Planechase 2012 | PC2 | 10 | 1 | 1 | 0 |
| 298 | Planechase Anthology | PCA | 10 | 1 | 1 | 0 |
| 35 | Battle Royale Box Set | BRB | 10 | 1 | 1 | 0 |
| 37 | Commander 2013 | C13 | 10 | 1 | 1 | 0 |
| 38 | Commander 2014 | C14 | 10 | 1 | 1 | 0 |
| 39 | Commander 2015 | C15 | 10 | 1 | 1 | 0 |
| 49 | Chronicles | CHR | 10 | 1 | 1 | 0 |
| 54 | Commander 2011 | CMD | 10 | 1 | 1 | 0 |
| 6 | Fourth Edition | 4ED | 10 | 1 | 1 | 0 |
| 8 | Fifth Edition | 5ED | 10 | 1 | 1 | 0 |
| 9 | Classic Sixth Edition | 6ED | 10 | 1 | 1 | 0 |

All 14 sets have:
- `isNonFoilOnly = 1` (integer)
- `NUM_TRANSLATIONS = 10` (indicating Japanese translation exists)

**Impact:**
* Current implementation: **537/551 matches (97.5%)**
* Corrected implementation: **551/551 matches (100%)**

---

## Result

**Perfect match with corrected logic**

**Sets where `HAS_JAPANESE_TRANSLATION_AND_ONLY_AVAILABLE_IN_NON_FOIL = 1`:**

* Battle Royale Box Set (BRB)
* Homelands (HML)
* Planechase Anthology (PCA)
* Ice Age (ICE)
* Fifth Edition (5ED)
* Archenemy (ARC)
* Chronicles (CHR)
* Fourth Edition (4ED)
* Classic Sixth Edition (6ED)
* Commander 2013 (C13)
* Commander 2011 (CMD)
* Commander 2014 (C14)
* Commander 2015 (C15)
* Planechase 2012 (PC2)

All 14 sets have Japanese translations AND are only available in non-foil format.
