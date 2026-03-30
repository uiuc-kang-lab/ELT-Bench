# Column Mismatch Summary

## Database: genes
## Table: genes__genes
## Column: INTERACTION_WITH_GENES_LOCATED_IN_THE_NUCLEUS_AND_IS_POSITIVELY_CORRELATED

### Description
Set to 1 if the gene's interaction is with genes located in the nucleus in which it is positively correlated

---

## Root Cause
**Interactions table is bidirectional: SQL only considers gene as GeneID1, but should consider both GeneID1 and GeneID2 positions**

### Incorrect SQL Logic
```sql
nucleus_interaction AS (
    SELECT DISTINCT
        i.GENEID1 as GENEID,
        1 as interaction_with_genes_located_in_the_nucleus_and_is_positively_correlated
    FROM interactions i
    INNER JOIN classification c ON i.GENEID2 = c.GENEID
    WHERE c.LOCALIZATION = 'nucleus'
        AND i.EXPRESSION_CORR > 0
)
```

### Correct SQL Logic
```sql
-- Check both directions: gene as GeneID1 or GeneID2
nucleus_interaction AS (
    SELECT DISTINCT GENEID
    FROM (
        -- Gene as GeneID1, partner (GeneID2) in nucleus
        SELECT i.GENEID1 as GENEID
        FROM {{ source('genes', 'INTERACTIONS') }} i
        INNER JOIN {{ source('genes', 'CLASSIFICATION') }} c ON i.GENEID2 = c.GENEID
        WHERE c.LOCALIZATION = 'nucleus'
            AND i.EXPRESSION_CORR > 0
        UNION
        -- Gene as GeneID2, partner (GeneID1) in nucleus
        SELECT i.GENEID2 as GENEID
        FROM {{ source('genes', 'INTERACTIONS') }} i
        INNER JOIN {{ source('genes', 'CLASSIFICATION') }} c ON i.GENEID1 = c.GENEID
        WHERE c.LOCALIZATION = 'nucleus'
            AND i.EXPRESSION_CORR > 0
    )
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** Check if a gene has ANY interaction (positive correlation) with a gene located in the nucleus.
* **What the SQL actually computes:** Only checks if the gene appears in GeneID1 and the partner (GeneID2) is in the nucleus.

The Interactions table stores bidirectional relationships. A gene can interact with a nucleus-localized gene whether it appears in GeneID1 or GeneID2:
- If gene X is in GeneID1 and its partner (GeneID2) is in the nucleus -> gene X interacts with a nucleus gene
- If gene X is in GeneID2 and its partner (GeneID1) is in the nucleus -> gene X ALSO interacts with a nucleus gene

---

## Evidence

**Key comparison demonstrating the error:**

| Gene | As GeneID1 | As GeneID2 | Has Nucleus Interaction | GT | Pred |
| ---- | ---------- | ---------- | ----------------------- | -- | ---- |
| G234065 | No nucleus partner | G237021 (nucleus, corr=0.753) | Yes | 1 | 0 |
| G234084 | No interactions | G237261 (nucleus, corr=0.746) | Yes | 1 | 0 |
| G234107 | No interactions | G234106 (nucleus, corr=0.178) | Yes | 1 | 0 |
| G234124 | No interactions | G234635 (nucleus, corr=0.772) | Yes | 1 | 0 |
| G234185 | No interactions | G235539 (nucleus, corr=0.479) | Yes | 1 | 0 |

**Detailed example - Gene G234065:**
- As GeneID1: 2 interactions, neither partner is in nucleus
  - G234371 (cytoplasm), G234854 (cytoplasm)
- As GeneID2: 4 interactions
  - G237021 is in nucleus with positive correlation (0.753)
- **Result:** Should be 1 (interacts with nucleus gene), but SQL returns 0 (only checked GeneID1 position)

**Impact:**
* Current implementation: **764/862 matches (88.6%)**
* Corrected implementation: **862/862 matches (100%)**

GT distribution: 0=576, 1=286
Pred distribution: 0=674, 1=188 (missing 98 genes that should be 1)

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The 98 genes that were incorrectly marked as 0 all have interactions with nucleus genes when they appear in the GeneID2 column. The SQL must check both directions to correctly identify all genes that interact with nucleus-localized genes.
