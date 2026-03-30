# SQL Column Debugging Task

## Configuration(s)
```
DATABASE: {DATABASE}
TABLE: {TABLE}
COLUMN(S): [{COL_1}, {COL_2}, ..., {COL_N}]
```

## Context
Debug SQL column implementation with mismatches between ground truth and predicted values.

**Column specification:** See the `{COLUMN}` column definition in the `{TABLE}` table section of `data_model.yaml`

## File Structure
Your working directory is `{DATABASE}/`:
```
{DATABASE}/
├── data_model.yaml                        # Contains column specification
├── gt/
│   └── {TABLE}.csv                        # Ground truth values
├── predicted/
│   └── {TABLE}.csv                        # Current predicted values
│   └── {TABLE}.sql                        # Current SQL implementation
├── source_schemas/
│   └── *.csv                              # Schema descriptions
└── source_tables/
    └── *.csv/*.jsonl/*.parquet            # Actual data
```

## Your Task

### Step 1: Read and Analyze (Token Efficient)
1. **Read `data_model.yaml`:**
   - Find the `{TABLE}` table definition
   - Extract the full specification for `{COLUMN}` (name, description, any constraints)

2. **Read `predicted/{TABLE}.sql`:**
   - Identify the SQL logic used for `{COLUMN}`
   - Extract the specific CTE or logic block that computes this column

3. **Read `source_schemas/*.csv` and `source_tables/*.csv|*.jsonl|*.parquet`:**
   - Understand available source tables and their columns
   - Identify relevant tables/columns for this column's logic

4. **Load comparison data:**
   - Load `gt/{TABLE}.csv` and `predicted/{TABLE}.csv`
   - Compare `{COLUMN}` values to identify mismatch pattern

### Step 2: Identify Potential Issues
Based on the column description and current SQL, consider:

### Step 3: Create Test Script
Create `debug.py` with this structure:
```python
import pandas as pd
import sqlite3

# Configuration from prompt
DATABASE = "{DATABASE}"
TABLE = "{TABLE}"
COLUMN = "{COLUMN}"

# Load ground truth and predicted
gt_df = pd.read_csv(f"gt/{TABLE}.csv")
predicted_df = pd.read_csv(f"predicted/{TABLE}.csv")

# [Continue with your implementation]
```

**Script must:**
1. Load ONLY source tables needed (check source_schemas to identify which ones)
2. Implement current SQL logic extracted from `predicted/{TABLE}.sql`
3. Create 3-5 alternative interpretations based on identified ambiguities
4. Test each against ground truth
5. Show detailed comparison

**Key requirements:**
- Use pandas + sqlite3
- Handle NaN values properly with pd.isna() checks
- Show data exploration (counts, samples, distributions)
- Compare each option vs ground truth with match statistics
- Identify which option(s) achieve perfect match

### Step 4: Output Format
```
================================================================================
CONFIGURATION
================================================================================
Database: {DATABASE}
Table: {TABLE}
Column: {COLUMN}

Column Specification:
[Show the description from data_model.yaml]

================================================================================
DATA EXPLORATION
================================================================================
Ground truth shape: (X, Y)
Predicted shape: (X, Y)
Column '{COLUMN}' value distribution:
  GT:   0: X, 1: Y
  Pred: 0: X, 1: Y

[Show sample mismatches]

================================================================================
CURRENT IMPLEMENTATION
================================================================================
SQL Logic:
[Show extracted SQL for this column]

Results:
Match with ground truth: False
Mismatches: X/Y (Z%)
Mismatch positions: [...]

================================================================================
OPTION 1: [Clear description of interpretation]
================================================================================
SQL Logic:
[Show SQL]

Results:
Match with ground truth: True/False
Mismatches: X/Y (Z%)

[Repeat for Options 2-5]

================================================================================
SUMMARY
================================================================================
Current:  X/Y matches (Z%)
Option 1: X/Y matches (Z%)
Option 2: X/Y matches (Z%)
...

✓ PERFECT MATCH: Option X
[or]
⚠ No perfect match found. Best: Option X with Y% accuracy
```

## Deliverables

1. **`debug.py`** - Complete test script
   - Add configuration variables at top
   - Include comments explaining each option's interpretation
   - Show clear output with all comparisons

2. **`summary_{DATABASE}_{TABLE}_{COLUMN}.md`** - Summary of findings with the following structure
    ## Database: {DATABASE}
    ## Table: {TABLE}
    ## Column: {COLUMN}

    **Description:**  
    [Exact column description from `data_model.yaml`, copied verbatim.]

    ---

    ## Root Cause
    **Concise statement of the core semantic or logical error**  
    (e.g., *Incorrect table used to count organizations*).

    ### Incorrect SQL Logic
    ```sql
    -- Minimal snippet: only the CTE / expression responsible for {COLUMN}
    ````

    ### Correct SQL Logic

    ```sql
    -- Minimal corrected CTE / expression
    ```

    ---

    ## Why the Original Logic Is Wrong

    * Clear, schema-grounded explanation of the mismatch
    * Explicitly contrast:

      * **What the column description means**
      * **What the SQL actually computes**
    * Reference table semantics (from `source_schemas`) only

    ---

    ## Evidence

    **Key comparison demonstrating the error:**

    | Entity | Wrong Logic | Correct Logic | Ground Truth |
    | ------ | ----------- | ------------- | ------------ |
    | ...    | ...         | ...           | ...          |

    **Impact:**

    * Current implementation: **X/Y matches (Z%)**
    * Corrected implementation: **X/Y matches (100%)**

    ---

    ## Result

    ✅ **Perfect match with corrected logic**

    **Entities where `{COLUMN} = 1`:**

    * Bullet list of entities that truly satisfy the condition


    **Example**: summary_has_over_organizations_and_an_inflation_rate_of_over_3_per.md
    ## Database: MONDIAL_GEO
    ## Table: countries
    ## Column: HAS_OVER_1_ORGANIZATIONS_AND_AN_INFLATION_RATE_OF_OVER_3_PER

    **Description:** Set to 1 if the country has over 1 organizations and an inflation rate of over 3, otherwise, set to 0.

    ---

    ### SQL Logic Error (Critical): The query uses the wrong table - `IS_MEMBER` (organization memberships) instead of `ORGANIZATION` (organizations hosted by the country).

    **Wrong SQL part:**
    ```sql
    organizations_and_inflation AS (
        SELECT
            c.CODE AS country_code,
            CASE
                WHEN COUNT(DISTINCT im.ORGANIZATION) > 1 AND MAX(e.INFLATION) > 3 THEN 1
                ELSE 0
            END AS has_over_1_organizations_and_an_inflation_rate_of_over_3_per
        FROM {{ source('airbyte_schema', 'COUNTRY') }} c
        LEFT JOIN {{ source('airbyte_schema', 'IS_MEMBER') }} im ON c.CODE = im.COUNTRY
        LEFT JOIN {{ source('airbyte_schema', 'ECONOMY') }} e ON c.CODE = e.COUNTRY
        GROUP BY c.CODE
    )
    ```

    **Corrected SQL part:**
    ```sql
    organizations_and_inflation AS (
        SELECT
            c.CODE AS country_code,
            CASE
                WHEN COUNT(o.Abbreviation) > 1 AND MAX(e.INFLATION) > 3 THEN 1
                ELSE 0
            END AS has_over_1_organizations_and_an_inflation_rate_of_over_3_per
        FROM {{ source('airbyte_schema', 'COUNTRY') }} c
        LEFT JOIN {{ source('airbyte_schema', 'ORGANIZATION') }} o ON c.CODE = o.COUNTRY
        LEFT JOIN {{ source('airbyte_schema', 'ECONOMY') }} e ON c.CODE = e.COUNTRY
        GROUP BY c.CODE
    )
    ```

    **Why It's Wrong:** The description says "the country has over 1 organizations" which means organizations that the country **hosts** (i.e., where the organization's headquarters are located), not organizations that the country is a **member** of.

    - `IS_MEMBER` table: Lists which countries are members of which organizations (e.g., USA is a member of UN, NATO, etc.) - almost every country is a member of dozens of organizations
    - `ORGANIZATION` table: Lists where organization headquarters are located (e.g., UN is hosted in USA, EU is hosted in Belgium) - only a few countries host multiple organizations

    **Example of the difference:**
    | Country | IS_MEMBER count (memberships) | ORGANIZATION count (hosted) | Inflation |
    |---------|------------------------------|----------------------------|-----------|
    | United States | 72 | 21 | 2.5% |
    | United Kingdom | 74 | 4 | 3.1% |
    | Italy | 71 | 2 | 5.4% |
    | Ethiopia | 37 | 2 | 10.0% |

    **Impact:**
    - Current (wrong) calculation: 152 countries have value = 1 (40.9% match rate)
    - Correct calculation: 6 countries have value = 1 (100% match rate)

    The 6 countries that correctly match GT=1 are those that **host** more than 1 organization AND have inflation > 3%:
    - United Kingdom (hosts 4 orgs: EBRD, IMO, Inmarsat, C)
    - Saudi Arabia (hosts 3 orgs: GCC, IDB, OIC)
    - Cote dIvoire (hosts 2 orgs: AfDB, Entente)
    - Ethiopia (hosts 2 orgs: ECA, OAU)
    - Italy (hosts 2 orgs: FAO, IFAD)
    - Indonesia (hosts 2 orgs: ASEAN, NAM)

## Execution Instructions

1. Read files in this order (token efficient):
   - `data_model.yaml` (only {TABLE}/{COLUMN} section)
   - `predicted/{TABLE}.sql` (only {COLUMN} logic)
   - `source_schemas/*.csv` (only relevant tables)
   - `gt/{TABLE}.csv` and `predicted/{TABLE}.csv` (only {COLUMN} column)

2. Create the test script with all options

3. Run it and generate findings document

4. Present both deliverables

Begin now by reading the necessary files from the folder {DATABASE} and creating the debugging script.