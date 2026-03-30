# Batch SQL Column Debugging Task

## Overview
Execute the task described in `prompt.md` for each database-table-column combination found in `stage2.log` where the column appears in the `Unmatched columns` array.

## Instructions

### Step 1: Parse stage2.log
Read `stage2.log` and extract all entries where `Unmatched columns` is non-empty.

The log format is:
```
Database: <database_name>
Table: <table_name>
Matched columns: [...]
Unmatched columns: ['COL_1', 'COL_2', ..., 'COL_N']
Missed: [...]
```

Note: When a new `Database:` line appears, it sets the current database for all subsequent tables until the next `Database:` line.

### Step 2: Build Work Queue
Create a list of (database, table, column) tuples for each column in non-empty `Unmatched columns` arrays.

For example, given:
```
Database: european_football_1
Table: eu_foolball__divisions
Matched columns: ['DIVISION', 'NAME', 'COUNTRY']
Unmatched columns: ['NUM_TEAMS_2012', 'HIGHEST_FINAL_TIME_SCORE_2021']
Missed: []

Database: superstore
Table: products
Matched columns: []
Unmatched columns: ['PRODUCT_ID', 'PRODUCT_NAME']
Missed: []
```

The work queue should be:
1. (european_football_1, eu_foolball__divisions, NUM_TEAMS_2012)
2. (european_football_1, eu_foolball__divisions, HIGHEST_FINAL_TIME_SCORE_2021)
3. (superstore, products, PRODUCT_ID)
4. (superstore, products, PRODUCT_NAME)

Skip any database-table combination where `Unmatched columns: []` is empty.

### Step 3: Process Each Item
For each (DATABASE, TABLE, COLUMN) tuple in the work queue:

1. **Set configuration variables:**
   - DATABASE = `<database_name>`
   - TABLE = `<table_name>`
   - COLUMN = `<column_name>`

2. **Execute the full task from `prompt.md`:**
   - Read and analyze the relevant files in `{DATABASE}/` directory
   - Identify potential issues with the column implementation
   - Create `{DATABASE}/debug.py` test script
   - Run the debug script
   - Create `{DATABASE}/summary_{DATABASE}_{TABLE}_{COLUMN}.md` with findings

3. **Track progress:**
   - Log which database-table-column is being processed
   - Report success/failure for each item
   - Continue to next item even if one fails

### Step 4: Summary Report
After processing all items, create a summary report `batch_debug_summary.md` containing:
- Total items processed
- Number of successful analyses
- Number of failures (with reasons)
- For each item: database, table, column, result (match found / no match / error)

## File Structure Reference
Each database folder should follow this structure:
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

## Execution
Begin by:
1. Reading `stage2.log`
2. Parsing all unmatched columns
3. Creating a todo list with all items to process
4. Processing each item sequentially, following the full `prompt.md` workflow for each

## Expected Output
For each unmatched column, you should produce:
- `{DATABASE}/debug.py` - Debug script
- `{DATABASE}/summary_{DATABASE}_{TABLE}_{COLUMN}.md` - Analysis summary

Plus a final `batch_debug_summary.md` with overall results.
