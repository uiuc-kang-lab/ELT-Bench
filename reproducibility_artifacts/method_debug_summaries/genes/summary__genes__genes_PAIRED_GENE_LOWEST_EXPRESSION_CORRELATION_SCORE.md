# Column Mismatch Summary

## Database: genes
## Table: genes__genes
## Column: PAIRED_GENE_LOWEST_EXPRESSION_CORRELATION_SCORE

### Description
The paired gene with the lowest expression correlation score, with ties broken by the ascending order of the geneid

---

## Root Cause
**Interactions table is bidirectional: SQL only considers gene as GeneID1, but should consider both GeneID1 and GeneID2 positions**

### Incorrect SQL Logic
```sql
lowest_corr AS (
    SELECT
        i.GENEID1 as GENEID,
        FIRST_VALUE(i.GENEID2) OVER (
            PARTITION BY i.GENEID1
            ORDER BY i.EXPRESSION_CORR ASC, i.GENEID2 ASC
        ) as paired_gene_lowest_expression_correlation_score
    FROM interactions i
    QUALIFY ROW_NUMBER() OVER (PARTITION BY i.GENEID1 ORDER BY i.EXPRESSION_CORR ASC, i.GENEID2 ASC) = 1
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

lowest_corr AS (
    SELECT
        GENEID,
        FIRST_VALUE(PAIRED_GENE) OVER (
            PARTITION BY GENEID
            ORDER BY EXPRESSION_CORR ASC, PAIRED_GENE ASC
        ) as paired_gene_lowest_expression_correlation_score
    FROM all_interactions
    QUALIFY ROW_NUMBER() OVER (PARTITION BY GENEID ORDER BY EXPRESSION_CORR ASC, PAIRED_GENE ASC) = 1
)
```

---

## Why the Original Logic Is Wrong

* **What the column description means:** For each gene, find the paired gene with the lowest expression correlation score across ALL interactions involving that gene.
* **What the SQL actually computes:** Only looks at interactions where the gene appears in the GeneID1 column, missing all interactions where the gene appears in GeneID2.

This is the same issue as PAIRED_GENE_HIGHEST_EXPRESSION_CORRELATION_SCORE but with ascending sort order for correlation values.

---

## Evidence

**Key comparison demonstrating the error:**

| Gene | Wrong Logic (GeneID1 only) | Correct Logic (both directions) | Ground Truth |
| ---- | -------------------------- | ------------------------------- | ------------ |
| G234065 | G234371 (corr=0.824) | G235042 (corr=-0.466) | G235042 |
| G234073 | G239976 (corr=0.358) | G234824 (corr=-0.187) | G234824 |
| G234074 | G234967 (corr=0.370) | G235158 (corr=0.194) | G235158 |
| G234103 | G234361 (corr=-0.064) | G235655 (corr=-0.105) | G235655 |
| G234139 | G234139 (corr=1.000) | G235014 (corr=0.457) | G235014 |

**Example match showing the difference:**
- Gene G234065 as GeneID1: lowest corr = 0.824 with G234371
- Gene G234065 as GeneID2: has interaction with G235042 (corr=-0.466)
- The actual lowest correlation is -0.466 with G235042, not 0.824 with G234371

**Impact:**
* Current implementation: **524/862 matches (60.8%)**
* Corrected implementation: **862/862 matches (100%)**

---

## Result
**Perfect match with corrected logic**

**Key insight:**
Same as for highest correlation - the Interactions table represents bidirectional relationships. The SQL must union both directions to find all interaction partners for a given gene, then find the one with the lowest correlation score.
