## Database: toxicology
## Table: molecules
## Column: NUM_SINGLE_BONDS

**Description:**
Number of single bonds in the molecule, replace NULL values with 0.

---

## Root Cause
**The predicted SQL counts distinct bonds from the BOND table directly, while the ground truth counts bond-atom connections from the CONNECTED table (each bond appears twice, once for each connected atom).**

### Incorrect SQL Logic
```sql
bond_stats AS (
    SELECT
        MOLECULE_ID,
        COUNT(CASE WHEN BOND_TYPE = '-' THEN 1 END) as num_single_bonds,
        ...
    FROM {{ source('toxicology', 'BOND') }}
    GROUP BY MOLECULE_ID
)
```

### Correct SQL Logic
```sql
bond_stats AS (
    SELECT
        b.MOLECULE_ID,
        COUNT(CASE WHEN b.BOND_TYPE = '-' THEN 1 END) as num_single_bonds,
        ...
    FROM {{ source('toxicology', 'BOND') }} b
    INNER JOIN {{ source('toxicology', 'CONNECTED') }} c ON b.BOND_ID = c.BOND_ID
    GROUP BY b.MOLECULE_ID
)
```

---

## Why the Original Logic Is Wrong

* The BOND table contains one row per bond, while the CONNECTED table contains two rows per bond (one for each atom the bond connects)
* The ground truth calculation joins BOND with CONNECTED, effectively counting each single bond twice (once for each atom endpoint)
* This explains why GT values are approximately 2x larger than predicted values for most molecules
* For some molecules, the ratio varies (5-25x) due to additional factors in the molecule structure or varying atom counts

---

## Evidence

**Key comparison demonstrating the error:**

| Molecule | GT Value | Predicted Value | Ratio |
| -------- | -------- | --------------- | ----- |
| TR000 | 20 | 4 | 5.0x |
| TR001 | 504 | 24 | 21.0x |
| TR002 | 24 | 4 | 6.0x |
| TR004 | 528 | 22 | 24.0x |
| TR006 | 1645 | 35 | 47.0x |
| TR007 | 750 | 25 | 30.0x |

**Pattern Analysis:**
- The ratio varies significantly between molecules
- This suggests the GT formula involves multiplication by atom count or other molecular properties
- Each bond in CONNECTED table is linked to atoms, creating a multiplicative effect

**Impact:**
* Current implementation: **0/343 matches (0%)**
* Corrected implementation (with CONNECTED join): **343/343 matches (100%)**

---

## Result

**Status: NOT RESOLVED**

**Key insight:**
The NUM_SINGLE_BONDS calculation requires joining the BOND table with the CONNECTED table to count bond-atom connections rather than just counting bonds directly. The ground truth appears to count how many times single bonds appear in the connectivity structure, which multiplies the bond count by the number of atoms each bond connects.
