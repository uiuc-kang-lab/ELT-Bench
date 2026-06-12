# Column Mismatch Summary

## Database: food_inspection_2
## Table: employees
## Column: IS_SANITARIAN_AND_HAS_INSPECTED_THE_FACILITY_BURBANK

**Description:**
Set to 1 if the employee is a Sanitarian and has inspected the facility in Burbank, otherwise, set to 0

---

## Root Cause
**Wrong interpretation of "Burbank": SQL looks for city = 'Burbank', but "Burbank" refers to a facility NAME (Burbank Elementary School), not a city**

### Incorrect SQL Logic
```sql
CASE
    WHEN e.title = 'Sanitarian'
        AND EXISTS (
            SELECT 1
            FROM inspection_data id2
            JOIN establishment_data ed ON id2.license_no = ed.license_no
            WHERE id2.employee_id = e.employee_id
            AND ed.city = 'Burbank'
        ) THEN 1
    ELSE 0
END as is_Sanitarian_and_has_inspected_the_facility_Burbank
```

### Correct SQL Logic
```sql
CASE
    WHEN e.title = 'Sanitarian'
        AND EXISTS (
            SELECT 1
            FROM inspection_data id2
            JOIN establishment_data ed ON id2.license_no = ed.license_no
            WHERE id2.employee_id = e.employee_id
            AND ed.dba_name LIKE '%Burbank%'
        ) THEN 1
    ELSE 0
END as is_Sanitarian_and_has_inspected_the_facility_Burbank
```

---

## Why the Original Logic Is Wrong

* **What the column description means:**
  * "The facility in Burbank" refers to an establishment named "Burbank" (specifically "Burbank Elementary School")
  * The phrase "the facility Burbank" indicates a specific named facility, not a geographic location

* **What the SQL actually computes:**
  * Looks for establishments where `city = 'Burbank'`
  * No establishments exist in the city of Burbank in this dataset
  * Result: Always returns 0 for all employees

**Data evidence:**
- Establishments with city = 'Burbank': **0**
- Establishments with 'Burbank' in dba_name: **1** (license_no: 22401, dba_name: "Burbank", aka_name: "Burbank Elementary School", city: "CHICAGO")

---

## Evidence

**Key comparison demonstrating the error:**

| Employee ID | Title | Wrong Logic (city) | Correct Logic (dba_name) | Ground Truth |
| ----------- | ----- | ------------------ | ------------------------ | ------------ |
| 104633 | Sanitarian | 0 | 1 | 1 |
| 106581 | Sanitarian | 0 | 1 | 1 |
| 118150 | Sanitarian | 0 | 1 | 1 |
| 138450 | Sanitarian | 0 | 1 | 1 |
| 143902 | Sanitarian | 0 | 1 | 1 |
| 153443 | Sanitarian | 0 | 1 | 1 |
| 158905 | Sanitarian | 0 | 1 | 1 |

**The facility "Burbank":**
- License No: 22401
- DBA Name: Burbank
- AKA Name: Burbank Elementary School
- City: CHICAGO (not Burbank)
- Type: School establishment

**Impact:**
* Current implementation: **68/75 matches (90.7%)**
* Corrected implementation: **75/75 matches (100%)**

---

## Result

**Perfect match with corrected logic**

The key insight is that "the facility Burbank" in the column description refers to a specific named establishment, not a city. The phrase uses "the facility" (singular, definite article) followed by a name, indicating it's referring to a facility called "Burbank" rather than facilities located in a city named Burbank.

**Employees who are Sanitarians and have inspected Burbank (the facility):**
- 7 employees qualify (Employee IDs: 104633, 106581, 118150, 138450, 143902, 153443, 158905)
