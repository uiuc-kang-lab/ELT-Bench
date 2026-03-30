# Column Mismatch Summary

## Database: genes
## Table: genes__genes
## Column: NUM_FUNCTIONS

### Description
The number of functions the gene has, replace NULL values with 0.

---

## Root Cause
**Semantic misinterpretation: "Number of functions" means count of function entries (rows), not count of DISTINCT function values**

### Incorrect SQL Logic
```sql
genes_functions AS (
    SELECT
        GENEID,
        COUNT(DISTINCT FUNCTION) as num_functions
    FROM {{ source('genes', 'GENES') }}
    WHERE FUNCTION IS NOT NULL
    GROUP BY GENEID
)
```

### Correct SQL Logic
```sql
genes_functions AS (
    SELECT
        GENEID,
        COUNT(FUNCTION) as num_functions
    FROM {{ source('genes', 'GENES') }}
    WHERE FUNCTION IS NOT NULL
    GROUP BY GENEID
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** Count the total number of function entries for each gene. The Genes table has multiple rows per gene, where each row represents a different combination of attributes (Class, Complex, Phenotype, Motif) with a Function value.
* **What the SQL actually computes:** Counts only unique function names, ignoring that the same function can appear in multiple attribute combinations.

The Genes table is denormalized - each gene can have multiple rows with different attribute combinations (Class, Motif, Phenotype, etc.), and each row has an associated Function. The "number of functions" refers to the total count of function entries (rows), not the count of distinct function types.

**Schema Context:**
- Genes table has columns: GeneID, Essential, Class, Complex, Phenotype, Motif, Chromosome, Function, Localization
- Each gene can have multiple rows representing different attribute combinations
- The Function column contains categorical values like "PROTEIN SYNTHESIS", "CELLULAR ORGANIZATION", etc.

---

## Evidence

**Key comparison demonstrating the error:**

| Gene | Total Rows | Unique Functions | Correct (COUNT) | Wrong (COUNT DISTINCT) | GT |
| ---- | ---------- | ---------------- | --------------- | ---------------------- | -- |
| G234064 | 4 | 2 | 4 | 2 | 4 |
| G234065 | 8 | 4 | 8 | 4 | 8 |
| G234070 | 6 | 3 | 6 | 3 | 6 |
| G234074 | 12 | 3 | 12 | 3 | 12 |
| G234227 | 60 | 6 | 60 | 6 | 60 |

**Detailed example - Gene G234064:**
- Rows in Genes table: 4
- Functions (with duplicates):
  - "CELLULAR ORGANIZATION (proteins are localized to the corresponding organelle)"
  - "PROTEIN SYNTHESIS"
  - "CELLULAR ORGANIZATION (proteins are localized to the corresponding organelle)"
  - "PROTEIN SYNTHESIS"
- Unique functions: 2
- Correct count (total rows): 4
- Wrong count (DISTINCT): 2
- Ground truth: 4

**Impact:**
* Current implementation: **517/862 matches (60.0%)**
* Corrected implementation: **862/862 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The Genes table represents gene attributes in a denormalized form where each row is a distinct attribute combination. When the description says "number of functions," it means the total count of function entries (rows) for that gene, not the number of unique function types. This makes semantic sense because each row represents a different context (e.g., different phenotype or motif) in which the gene performs that function.
