# Column Mismatch Summary

## Database: synthea
## Table: synthea__patients
## Column: TIME_RECIEVE_MOST_RECENT_VACCINE

**Description:**
The time when the patient received her/his most recent influenza seasonal vaccine

---

## Root Cause
**Incorrect vaccine filter: SQL filters for only influenza vaccines, but GT uses ANY immunization**

### Incorrect SQL Logic
```sql
most_recent_influenza AS (
    SELECT
        PATIENT,
        MAX(DATE) AS time_recieve_most_recent_vaccine
    FROM {{ source('airbyte_schema', 'IMMUNIZATIONS') }}
    WHERE DESCRIPTION = 'Influenza  seasonal  injectable  preservative free'
    GROUP BY PATIENT
)
```

### Correct SQL Logic
```sql
most_recent_vaccine AS (
    SELECT
        PATIENT,
        MAX(DATE) AS time_recieve_most_recent_vaccine
    FROM {{ source('airbyte_schema', 'IMMUNIZATIONS') }}
    GROUP BY PATIENT
)
```

---

## Why the Original Logic Is Wrong

* **What the column description says**: "The time when the patient received her/his most recent **influenza seasonal vaccine**"
* **What the GT actually computes**: The most recent date of **ANY immunization** (DTaP, Hep A, IPV, etc.)

The column description explicitly mentions "influenza seasonal vaccine", but the ground truth data shows that it actually returns the maximum date from ALL immunization records, regardless of vaccine type.

For example:
- **Sachiko Stracke** has influenza immunizations on `2015-11-10` and `2016-12-03`
- But GT returns `2017-07-12` - the date of her **Hep A** immunization
- The SQL correctly filters for influenza (`2016-12-03`) but GT wants ANY immunization (`2017-07-12`)

The `IMMUNIZATIONS` table contains many vaccine types:
- `Influenza seasonal injectable preservative free` (7,247 records)
- `DTaP` (742 records)
- `IPV` (593 records)
- `Hep B adolescent or pediatric` (458 records)
- etc.

---

## Evidence

**Key comparison demonstrating the error:**

| Patient | Name | Wrong Logic (Flu Only) | Correct Logic (Any Immunization) | Ground Truth |
| ------- | ---- | ---------------------- | -------------------------------- | ------------ |
| 047ce05d... | Sachiko Stracke | 2016-12-03 | 2017-07-12 | 2017-07-12 |
| 07ddc799... | Enrique Ritchie | 2016-10-20 | 2017-08-10 | 2017-08-10 |
| 1cf1cd29... | Marcus Koepp | NULL | 2017-09-24 | 2017-09-24 |
| 2ad29b71... | Dean Conn | 2016-10-15 | 2017-08-07 | 2017-08-07 |
| 35a2f55b... | Ethel Cormier | 2017-02-27 | 2017-09-24 | 2017-09-24 |
| 399d36c2... | Dwayne Little | 2017-03-31 | 2017-09-18 | 2017-09-18 |

**What immunization types appear on GT dates (examples):**

| Patient | GT Date | Immunization on GT Date |
| ------- | ------- | ----------------------- |
| Sachiko Stracke | 2017-07-12 | Hep A ped/adol 2 dose |
| Enrique Ritchie | 2017-08-10 | DTaP |
| Marcus Koepp | 2017-09-24 | Hep B adolescent or pediatric |
| Dean Conn | 2017-08-07 | DTaP |
| Gaston Okuneva | 2017-10-15 | rotavirus, DTaP, Hib, PCV 13, IPV |

**Impact:**
* Current implementation: **1430/1462 matches (97.8%)**
* Corrected implementation: **1462/1462 matches (100%)**

---

## Result

✅ **Perfect match with corrected logic**

**Key insight:**
Despite the column description explicitly mentioning "influenza seasonal vaccine", the ground truth actually computes `MAX(DATE)` from ALL immunization records without filtering by vaccine type. The SQL implementation correctly interprets the description but the GT uses a different (broader) definition.

**The 32 mismatched patients** are those who received other immunizations (like DTaP, Hep A, Hep B, etc.) after their last influenza vaccine, or who never received an influenza vaccine but have other immunizations on record.
