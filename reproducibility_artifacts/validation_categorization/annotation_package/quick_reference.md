# Error Classification Quick Reference Card

**Print this or keep it open while annotating!**

---

## Decision Tree

```
┌─ Do the values actually match? ──────────────► 5.x FALSE POSITIVE
│
├─ Is the schema description ambiguous? ───────► 1. AMBIGUOUS DESCRIPTION
│
├─ Is it specifically a JOIN type issue? ──────► 3. JOIN ISSUES
│
├─ Is it specifically NULL handling? ──────────► 7. NULL HANDLING
│
├─ Is it specifically key generation? ─────────► 8. KEY GENERATION
│
├─ Missing a required JOIN? ───────────────────► 4.1 MISSING JOIN
│
├─ Using wrong table/column? ──────────────────► 4.2 WRONG TABLE/COLUMN
│
├─ Requires domain knowledge not in docs? ─────► 6. DOMAIN KNOWLEDGE
│
├─ GT uses undocumented calculation? ──────────► 9. UNKNOWN CALCULATION
│
└─ SQL logic is flawed? ───────────────────────► 2. LOGIC ERROR
```

---

## Categories at a Glance

### AGENT ERRORS (fix the AI)

| # | Category | Key Question |
|---|----------|-------------|
| **1** | **Ambiguous Description** | Could a reasonable person interpret this differently? |
| **2** | **Logic Error** | Is the SQL calculation/filter/aggregation wrong? |
| **3** | **JOIN Issues** | Wrong INNER/LEFT/OUTER JOIN causing missing/extra rows? |
| **4.1** | **Missing Join** | Forgot to join to a required table? |
| **4.2** | **Wrong Table/Column** | Used wrong table or selected wrong column? |
| **6** | **Domain Knowledge** | Requires business knowledge not documented? |
| **7** | **NULL Handling** | Wrong NULL filter, ordering, or replacement? |
| **8** | **Key Generation** | Primary key created differently? |

### BENCHMARK ERRORS (fix the benchmark)

| # | Category | Key Question |
|---|----------|-------------|
| **5.1** | **Actual Match** | Do values actually match identically? |
| **5.2** | **Format Mismatch** | Same value, different format (0.5 vs 50%)? |
| **5.3** | **Duplicated Rows** | GT has wrong duplicate rows? |
| **5.4** | **NULL Mismatch** | Different NULL handling, both valid? |
| **5.5** | **Row Ordering** | Only ORDER BY differs? |
| **5.6** | **Other False Positive** | Other evaluation artifact? |
| **9** | **Unknown Calculation** | GT uses undocumented rules? |

---

## Common Patterns

### Pattern: "Used wrong column"
- **If description was ambiguous about which column** → **1** (Ambiguous)
- **If description clearly specified correct column** → **4.2** (Wrong Column)

### Pattern: "Values don't match"
- **Check if they're actually the same** (0.5 vs 50%) → **5.2** (Format Mismatch)
- **Check if only ordering differs** → **5.5** (Row Ordering)
- **If truly different, why?** → Determine root cause

### Pattern: "NULL issues"
- **Schema says how to handle NULLs, agent didn't follow** → **7** (NULL Handling)
- **Schema silent, both approaches valid** → **5.4** (NULL Mismatch)

### Pattern: "Wrong aggregation"
- **SQL uses COUNT when should SUM** → **2** (Logic Error)
- **Wrong GROUP BY scope** → **2** (Logic Error)

---

## Priority Rules

When multiple categories fit, choose in this order:

1. **False Positives (5.x)** - If not a real error, stop here
2. **Specific > General** - Use 3, 4.1, 4.2, 6, 7, 8 when they apply
3. **Root Cause > Symptom** - Why did the error happen?
4. **Ambiguous (1) vs Logic (2)** - Could anyone interpret it differently?

---

## Examples

### ✓ Category 1 (Ambiguous)
- "Snowy day" → Could mean weather code OR snowfall measurement
- "International shipping" → Could mean different countries OR non-USA

### ✓ Category 2 (Logic Error)
- COUNT distinct products when should SUM quantities
- Average includes zero-purchase customers when shouldn't

### ✓ Category 3 (JOIN Issues)
- INNER JOIN drops campaigns with missing advertiser data
- Should use LEFT JOIN to preserve all rows

### ✓ Category 4.1 (Missing Join)
- Query needs user name but doesn't join to users table

### ✓ Category 4.2 (Wrong Table/Column)
- Uses user_reviews table only, missing apps without reviews
- Uses codesum column when should use snowfall column

### ✓ Category 5.1 (Actual Match)
- All values match to 16 decimals but still flagged

### ✓ Category 5.2 (Format Mismatch)
- Agent: 0.456, GT: 45.6% (both mean 45.6%)

### ✓ Category 5.5 (Row Ordering)
- All values match by key, just different ORDER BY

### ✓ Category 6 (Domain Knowledge)
- "Winnings" in racing → Agent thinks victories, really means points

### ✓ Category 7 (NULL Handling)
- Description says "replace NULL with 0", agent keeps NULL
- Agent filters WHERE price IS NOT NULL, returns no results for all-NULL menus

### ✓ Category 8 (Key Generation)
- Agent uses hash-based ID, GT uses sequential ID

### ✓ Category 9 (Unknown Calculation)
- GT shows 156.7 but no interpretation of schema yields this

---

## Output Format

```
database__table__COLUMN | category_number
```

Example:
```
sales__customers__ABOVE_AVERAGE_BOUGHT_QUANTITY | 2
books__authors__AUTHOR_ID | 3
menu__menus__DISH_WITH_HIGHEST_PRICE | 7
```

---

**Remember:** Focus on the ROOT CAUSE, not just the symptom!
