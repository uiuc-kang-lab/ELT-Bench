# Column Mismatch Summary

## Database: genes
## Table: genes__genes
## Column: PAIRED_GENE_HIGHEST_EXPRESSION_CORRELATION_SCORE

### Description
The paired gene with the highest expression correlation score, with ties broken by the ascending order of the geneid

---

## Root Cause
**Interactions table is bidirectional: SQL only considers gene as GeneID1, but should consider both GeneID1 and GeneID2 positions**

### Incorrect SQL Logic
```sql
highest_corr AS (
    SELECT
        i.GENEID1 as GENEID,
        FIRST_VALUE(i.GENEID2) OVER (
            PARTITION BY i.GENEID1
            ORDER BY i.EXPRESSION_CORR DESC, i.GENEID2 ASC
        ) as paired_gene_highest_expression_correlation_score
    FROM interactions i
    QUALIFY ROW_NUMBER() OVER (PARTITION BY i.GENEID1 ORDER BY i.EXPRESSION_CORR DESC, i.GENEID2 ASC) = 1
)
```

### Correct SQL Logic
```sql
-- Combine both directions of interactions
all_interactions AS (
    SELECT GENEID1 as GENEID, GENEID2 as PAIRED_GENE, EXPRESSION_CORR
    FROM {{ source('genes', 'INTERACTIONS') }}
    UNION ALL
    SELECT GENEID2 as GENEID, GENEID1 as PAIRED_GENE, EXPRESSION_CORR
    FROM {{ source('genes', 'INTERACTIONS') }}
),

highest_corr AS (
    SELECT
        GENEID,
        FIRST_VALUE(PAIRED_GENE) OVER (
            PARTITION BY GENEID
            ORDER BY EXPRESSION_CORR DESC, PAIRED_GENE ASC
        ) as paired_gene_highest_expression_correlation_score
    FROM all_interactions
    QUALIFY ROW_NUMBER() OVER (PARTITION BY GENEID ORDER BY EXPRESSION_CORR DESC, PAIRED_GENE ASC) = 1
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** For each gene, find the paired gene with the highest expression correlation score across ALL interactions involving that gene.
* **What the SQL actually computes:** Only looks at interactions where the gene appears in the GeneID1 column, missing all interactions where the gene appears in GeneID2.

The Interactions table stores gene-gene interactions where each row represents a bidirectional relationship:
- `GeneID1` and `GeneID2` are both interacting genes
- The `Expression_Corr` applies equally to both genes in the pair

When looking for a gene's highest correlation partner, we need to consider:
1. All genes in `GeneID2` where our gene is in `GeneID1`
2. All genes in `GeneID1` where our gene is in `GeneID2`

---

## Evidence

**Key comparison demonstrating the error:**

| Gene | Wrong Logic (GeneID1 only) | Correct Logic (both directions) | Ground Truth |
| ---- | -------------------------- | ------------------------------- | ------------ |
| G234073 | G234065 (corr=0.749) | G238190 (corr=0.892) | G238190 |
| G234084 | NULL | G237261 (corr=0.746) | G237261 |
| G234103 | G234529 (corr=0.539) | G235213 (corr=0.457*) | G235213 |
| G234107 | NULL | G234849 (corr=0.650) | G234849 |
| G234240 | G234830 (corr=0.568) | G234368 (corr=0.642) | G234368 |

**Example match showing the difference:**
- Gene G234073 has 6 interactions as GeneID1 (max corr=0.749 with G234065)
- Gene G234073 has 3 interactions as GeneID2 (max corr=0.892 with G238190)
- The actual highest correlation is 0.892 with G238190, not 0.749 with G234065

**Impact:**
* Current implementation: **551/862 matches (63.9%)**
* Corrected implementation: **862/862 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
The Interactions table represents bidirectional relationships. Gene G234073 interacts with G238190 regardless of which column each appears in. The SQL must union both directions to find all interaction partners for a given gene.
