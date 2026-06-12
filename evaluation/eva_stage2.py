import snowflake.connector
import pandas as pd
import os
import numpy as np
import json
import argparse
import re
import warnings

# Suppress pandas warning about DBAPI2 connections (snowflake.connector works fine)
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

file_path = '../setup/destination/snowflake_credential.json'
SNOWFLAKE_CONFIG = read_json(file_path)

parser = argparse.ArgumentParser(description="agent")
parser.add_argument("--folder", type=str, required=True, help='Specify the folder name where you want to store the results.')
parser.add_argument("--example_index", type=str, required=False, default=None, help='Specify problem index range (e.g., 0-99, 0-4, 2,5,7)')
args = parser.parse_args()


def normalize_value(val):
    """
    Normalize a single value for comparison.
    Handles: surrounding quotes (when GT has extra quotes not in source)
    """
    if pd.isna(val):
        return val
    if isinstance(val, str):
        # Remove surrounding double or single quotes (e.g., '"regular"' -> 'regular')
        # This handles cases where GT added quotes not present in source
        if len(val) >= 2:
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
        return val
    return val


def try_parse_numeric(val):
    """
    Try to parse a value as numeric.
    Returns (is_numeric, numeric_value).
    Note: Does NOT handle comma-formatted strings - those are genuine format differences.
    """
    if pd.isna(val):
        return False, val
    if isinstance(val, (int, float, np.floating, np.integer)):
        return True, float(val)
    if isinstance(val, str):
        try:
            cleaned = val.strip()
            return True, float(cleaned)
        except (ValueError, TypeError):
            return False, val
    return False, val


def normalize_timestamp(val, truncate_to_day=False):
    """
    Normalize timestamp values to handle precision differences.
    Converts to datetime and truncates to seconds (or day if specified).
    """
    if pd.isna(val):
        return val
    try:
        dt = pd.to_datetime(val)
        if truncate_to_day:
            return dt.floor('D')
        return dt.floor('s')
    except:
        return val


def is_timestamp_column(series):
    """
    Check if a column contains timestamp values.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    sample = non_null.iloc[0]
    if isinstance(sample, str):
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}',
            r'\d{4}-\d{2}-\d{2}$'
        ]
        for pattern in timestamp_patterns:
            if re.match(pattern, str(sample)):
                return True
    return False


def is_date_only_column(series):
    """
    Check if a column contains date-only values (no time component).
    Returns True if majority of values are date-only format (YYYY-MM-DD).
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    date_only_pattern = r'^\d{4}-\d{2}-\d{2}$'
    date_only_count = 0

    for val in non_null:
        if isinstance(val, str) and re.match(date_only_pattern, val.strip()):
            date_only_count += 1

    # Consider it date-only if >80% of values match the pattern
    return date_only_count / len(non_null) > 0.8


def check_percentage_scale(v1, v2):
    """
    Check if one column is 100x the other (0-1 vs 0-100 scale).
    Returns scaling factor if detected, 1 otherwise.
    """
    v1_numeric = pd.to_numeric(v1, errors='coerce')
    v2_numeric = pd.to_numeric(v2, errors='coerce')

    valid_mask = v1_numeric.notna() & v2_numeric.notna() & (v1_numeric != 0)
    if valid_mask.sum() < 3:
        return 1

    ratios = v2_numeric[valid_mask] / v1_numeric[valid_mask]
    median_ratio = ratios.median()

    if 95 <= median_ratio <= 105:
        return 100
    elif 0.0095 <= median_ratio <= 0.0105:
        return 0.01
    return 1


def normalize_boolean(val):
    """
    Normalize boolean values to handle True/False vs 1/0 vs 'True'/'False'.
    """
    if pd.isna(val):
        return val
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, str):
        val_lower = val.lower().strip()
        if val_lower in ('true', '1', 'yes'):
            return 1
        elif val_lower in ('false', '0', 'no'):
            return 0
    if isinstance(val, (int, float, np.integer, np.floating)):
        if val == 1 or val == 1.0:
            return 1
        elif val == 0 or val == 0.0:
            return 0
    return val


def is_boolean_column(series):
    """
    Check if a column appears to be boolean (only contains 0, 1, True, False, etc.).
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    unique_vals = set()
    for val in non_null:
        if isinstance(val, bool):
            unique_vals.add(val)
        elif isinstance(val, str):
            val_lower = val.lower().strip()
            if val_lower in ('true', 'false', '1', '0', 'yes', 'no'):
                unique_vals.add(val_lower)
            else:
                return False
        elif isinstance(val, (int, float, np.integer, np.floating)):
            if val in (0, 1, 0.0, 1.0):
                unique_vals.add(int(val))
            else:
                return False
        else:
            return False

    return len(unique_vals) <= 2


def identify_primary_key_columns(df):
    """
    Identify likely primary key columns (ID columns).
    Returns list of column names that look like primary keys.
    """
    pk_patterns = [
        r'.*_id$',
        r'.*id$',
        r'^id$',
        r'.*_code$',
        r'.*_key$',
    ]

    pk_cols = []
    for col in df.columns:
        col_lower = col.lower()
        for pattern in pk_patterns:
            if re.match(pattern, col_lower):
                # Verify it has mostly unique values
                if df[col].nunique() >= len(df) * 0.5:
                    pk_cols.append(col)
                    break

    return pk_cols


def normalize_dataframe(df):
    """
    Normalize DataFrame for comparison:
    - Remove duplicate rows
    """
    df_norm = df.copy()
    df_norm = df_norm.drop_duplicates()

    return df_norm


def align_dataframes_by_key(df_gt, df_pred):
    """
    Align two dataframes by identifying and using primary key columns.
    Returns aligned dataframes with matching rows.

    Handles three cases:
    1. PK is unique in both - simple sort by PK
    2. PK has duplicates but same row count - sort by all common columns (e.g., microsoft_ads)
    3. PK has duplicates and different row count - deduplicate and merge on PK (e.g., superstore)
    """
    # Find common columns (sorted for deterministic order)
    common_cols = sorted(list(set(df_gt.columns) & set(df_pred.columns)))

    if not common_cols:
        return df_gt.reset_index(drop=True), df_pred.reset_index(drop=True), None

    # Identify potential PK columns from common columns
    # Prioritize _id columns over _name columns
    # Skip surrogate/hash key columns (UNIQUE_*, hash-like values)
    pk_candidates = []

    # Columns to skip - surrogate keys that may differ between GT and Pred
    skip_patterns = [r'^unique_.*', r'.*_surrogate.*', r'.*_hash.*']

    # First pass: look for _id columns (highest priority)
    id_patterns = [r'.*_id$', r'.*id$', r'^id$']
    for col in common_cols:
        col_lower = col.lower()
        # Skip surrogate key columns
        if any(re.match(sp, col_lower) for sp in skip_patterns):
            continue
        for pattern in id_patterns:
            if re.match(pattern, col_lower):
                if df_gt[col].nunique() >= len(df_gt) * 0.8:
                    pk_candidates.append(col)
                break

    # Second pass: if no _id columns found, try other patterns
    if not pk_candidates:
        other_patterns = [r'.*_code$', r'.*_key$', r'.*_name$', r'^name$']
        for col in common_cols:
            col_lower = col.lower()
            # Skip surrogate key columns
            if any(re.match(sp, col_lower) for sp in skip_patterns):
                continue
            for pattern in other_patterns:
                if re.match(pattern, col_lower):
                    if df_gt[col].nunique() >= len(df_gt) * 0.8:
                        pk_candidates.append(col)
                    break

    if not pk_candidates:
        # Fall back to first column that has high uniqueness (still skip surrogates)
        for col in common_cols:
            col_lower = col.lower()
            if any(re.match(sp, col_lower) for sp in skip_patterns):
                continue
            if df_gt[col].nunique() >= len(df_gt) * 0.8:
                pk_candidates.append(col)
                break

    # If we have a PK candidate, use it for alignment
    if pk_candidates:
        pk_col = pk_candidates[0]

        # Convert PK to string for consistent matching
        df_gt[pk_col] = df_gt[pk_col].astype(str)
        df_pred[pk_col] = df_pred[pk_col].astype(str)

        # Check if PK has duplicates in either dataframe
        gt_has_dups = df_gt[pk_col].duplicated().any()
        pred_has_dups = df_pred[pk_col].duplicated().any()

        if gt_has_dups or pred_has_dups:
            # Case: PK has duplicates
            if len(df_gt) == len(df_pred):
                # Same row count - sort by all common columns (e.g., microsoft_ads case)
                # Rows have same PK but differ by other attributes
                try:
                    sort_cols = sorted(common_cols)
                    df_gt_sorted = df_gt.sort_values(by=sort_cols).reset_index(drop=True)
                    df_pred_sorted = df_pred.sort_values(by=sort_cols).reset_index(drop=True)
                    return df_gt_sorted, df_pred_sorted, None
                except:
                    pass
            else:
                # Different row count - deduplicate on PK and merge (e.g., superstore case)
                # One dataframe has duplicate PKs that the other doesn't have
                try:
                    # Deduplicate both on PK (keep first occurrence)
                    df_gt_dedup = df_gt.drop_duplicates(subset=[pk_col], keep='first')
                    df_pred_dedup = df_pred.drop_duplicates(subset=[pk_col], keep='first')

                    # Find common keys
                    common_keys = set(df_gt_dedup[pk_col]) & set(df_pred_dedup[pk_col])

                    if len(common_keys) > 0:
                        # Filter to common keys and sort by PK
                        df_gt_filtered = df_gt_dedup[df_gt_dedup[pk_col].isin(common_keys)].sort_values(by=pk_col).reset_index(drop=True)
                        df_pred_filtered = df_pred_dedup[df_pred_dedup[pk_col].isin(common_keys)].sort_values(by=pk_col).reset_index(drop=True)
                        return df_gt_filtered, df_pred_filtered, pk_col
                except:
                    pass
        else:
            # PK is unique in both - simple alignment
            common_keys = set(df_gt[pk_col]) & set(df_pred[pk_col])

            if len(common_keys) > 0:
                df_gt_filtered = df_gt[df_gt[pk_col].isin(common_keys)].sort_values(by=pk_col).reset_index(drop=True)
                df_pred_filtered = df_pred[df_pred[pk_col].isin(common_keys)].sort_values(by=pk_col).reset_index(drop=True)
                return df_gt_filtered, df_pred_filtered, pk_col

    # Last resort: sort by all common columns
    try:
        sort_cols = sorted(common_cols)
        df_gt_sorted = df_gt.sort_values(by=sort_cols).reset_index(drop=True)
        df_pred_sorted = df_pred.sort_values(by=sort_cols).reset_index(drop=True)
        return df_gt_sorted, df_pred_sorted, None
    except:
        return df_gt.reset_index(drop=True), df_pred.reset_index(drop=True), None


def check_corretness(df_gt, df):

    matched_cols = []
    unmatched_cols = []
    missed_cols = []

    df_gt_norm = normalize_dataframe(df_gt)
    df_norm = normalize_dataframe(df)

    # Align dataframes by primary key
    df_gt_aligned, df_pred_aligned, pk_col = align_dataframes_by_key(df_gt_norm.copy(), df_norm.copy())

    def vectors_match(v1, v2, tol=1e-2):
        v1 = v1.reset_index(drop=True)
        v2 = v2.reset_index(drop=True)

        if len(v1) != len(v2):
            return False

        v1_normalized = v1.apply(normalize_value)
        v2_normalized = v2.apply(normalize_value)

        # Check for timestamp columns
        if is_timestamp_column(v1) or is_timestamp_column(v2):
            # Check if one side has date-only and the other has full timestamp
            # If so, truncate both to day level for fair comparison
            v1_date_only = is_date_only_column(v1)
            v2_date_only = is_date_only_column(v2)
            truncate_to_day = (v1_date_only != v2_date_only)  # Mismatch in precision

            v1_normalized = v1.apply(lambda x: normalize_timestamp(x, truncate_to_day))
            v2_normalized = v2.apply(lambda x: normalize_timestamp(x, truncate_to_day))

        # Check for boolean columns
        if is_boolean_column(v1) or is_boolean_column(v2):
            v1_normalized = v1.apply(normalize_boolean)
            v2_normalized = v2.apply(normalize_boolean)

        # Check for percentage scaling
        scale_factor = check_percentage_scale(v1_normalized, v2_normalized)
        if scale_factor != 1:
            v2_numeric = pd.to_numeric(v2_normalized, errors='coerce')
            v2_normalized = v2_numeric / scale_factor

        match_count = 0
        total_count = 0
        for a, b in zip(v1_normalized, v2_normalized):
            total_count += 1

            # Both null
            if pd.isna(a) and pd.isna(b):
                match_count += 1
                continue

            # Null vs 0 equivalence
            if (pd.isna(a) or a == 0) and (pd.isna(b) or b == 0):
                match_count += 1
                continue

            # One null, other not
            if pd.isna(a) or pd.isna(b):
                continue

            # Try to parse both as numeric (handles comma-formatted strings like "54,991")
            a_is_num, a_float = try_parse_numeric(a)
            b_is_num, b_float = try_parse_numeric(b)

            # Numeric comparison with tolerance
            if a_is_num and b_is_num:
                # Both zero
                if a_float == 0 and b_float == 0:
                    match_count += 1
                    continue

                # One zero, check if other is very small
                if a_float == 0:
                    if abs(b_float) <= tol:
                        match_count += 1
                    continue
                if b_float == 0:
                    if abs(a_float) <= tol:
                        match_count += 1
                    continue

                # Relative tolerance check (within 1%)
                rel_diff = abs(a_float - b_float) / max(abs(a_float), abs(b_float))
                if rel_diff <= 0.01:
                    match_count += 1
                    continue

                # Absolute tolerance for small numbers
                if abs(a_float - b_float) <= tol:
                    match_count += 1
                    continue

                # Check for floating point precision (e.g., 622.3672 vs 622.3672000000001)
                if abs(a_float - b_float) < 1e-6:
                    match_count += 1
                    continue

            elif isinstance(a, pd.Timestamp) and isinstance(b, pd.Timestamp):
                if a == b:
                    match_count += 1
                continue
            else:
                # String comparison
                if str(a) == str(b):
                    match_count += 1
                    continue
                # Case-insensitive comparison
                if str(a).lower() == str(b).lower():
                    match_count += 1
                    continue

        # Require 100% match (strict matching)
        if total_count == 0:
            return True
        return match_count == total_count

    tolerance = 1e-7

    for gold_col in df_gt_aligned.columns:
        if gold_col in df_pred_aligned.columns:
            if not vectors_match(df_gt_aligned[gold_col], df_pred_aligned[gold_col], tolerance):
                unmatched_cols.append(gold_col)
            else:
                matched_cols.append(gold_col)
        else:
            missed_cols.append(gold_col)

    with open(f'../data/results/{args.folder}/stage2.log', 'a') as f:
        f.write(f"Matched columns: {matched_cols}\n")
        f.write(f"Unmatched columns: {unmatched_cols}\n")
        f.write(f"Missed: {missed_cols}\n\n\n")

    return matched_cols, unmatched_cols, missed_cols


def filter_databases(databases, example_index):
    """Filter databases based on example_index parameter."""
    if example_index is None:
        return databases

    # Parse example_index (e.g., "0-99", "0-4", "2,5,7")
    indices = set()
    for part in example_index.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            indices.update(range(int(start), int(end) + 1))
        else:
            indices.add(int(part))

    # Filter databases by index
    return [db for i, db in enumerate(databases) if i in indices]


def evaluate_stage2(folder, snowflake_config, example_index=None):
    databases = []
    with open(f'../data/results/{folder}/stage1.log', 'r') as f:
        for line in f:
            s = line.split(' ')
            if s[0] == 'Success:':
                databases.append(s[1])

    # Apply example_index filter if provided
    if example_index is not None:
        all_dbs = [f.name for f in os.scandir('../tasks') if f.is_dir()]
        all_dbs.sort()
        filtered_dbs = set(filter_databases(all_dbs, example_index))
        databases = [db for db in databases if db in filtered_dbs]

    print(f"\n{'='*60}")
    print(f"STAGE 2: Data Correctness Verification")
    print(f"{'='*60}")
    print(f"Evaluating {len(databases)} database(s) that passed Stage 1...\n")

    log_file = f'../data/results/{folder}/stage2.log'

    for idx, db in enumerate(databases, 1):
        tables = [f.name for f in os.scandir(f'./{db}') if f.is_file() and f.name.endswith('.sql')]
        print(f"[{idx}/{len(databases)}] Evaluating data correctness for database: {db}")
        print(f"    Checking {len(tables)} table(s)...")
        with open(log_file, 'a') as f:
            f.write(f'Database: {db}\n')

        db_matched = 0
        db_unmatched = 0
        db_missed = 0
        db_errors = 0

        for table in tables:
            table = table.split('.')[0]
            with open(log_file, 'a') as f:
                f.write(f'Table: {table}\n')
            try:
                if not os.path.exists(f'../data/results/{folder}/{db}/{table}.csv'):
                    conn = snowflake.connector.connect(**snowflake_config)
                    with open(f'./{db}/{table}.sql', 'r') as f:
                        query = f.read()
                    df = pd.read_sql(query, conn)
                    os.makedirs(f'../data/results/{folder}/{db}', exist_ok=True)
                    df.to_csv(f'../data/results/{folder}/{db}/{table}.csv', index=False)
                    conn.close()
                df = pd.read_csv(f'../data/results/{folder}/{db}/{table}.csv')
                df_gt = pd.read_csv(f'../data/ground_truth/{db}/{table}.csv')
                matched, unmatched, missed = check_corretness(df_gt, df)
                db_matched += len(matched)
                db_unmatched += len(unmatched)
                db_missed += len(missed)

                status = "PASS" if len(unmatched) == 0 and len(missed) == 0 else "FAIL"
                print(f"      - {table}: {status} (matched: {len(matched)}, unmatched: {len(unmatched)}, missed: {len(missed)})")
            except Exception as e:
                db_errors += 1
                print(f"      - {table}: ERROR - {str(e)[:50]}...")
                with open(log_file, 'a') as f:
                    f.write(f'Error: {e}\n\n\n')

        total_cols = db_matched + db_unmatched + db_missed
        if total_cols > 0:
            accuracy = (db_matched / total_cols) * 100
            print(f"    Summary: {db_matched}/{total_cols} columns matched ({accuracy:.1f}% accuracy)")
        if db_errors > 0:
            print(f"    Errors: {db_errors} table(s) failed to evaluate")

    print(f"\nStage 2 complete. Log written to: {log_file}")
