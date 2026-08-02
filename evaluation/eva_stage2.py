"""
Stage-2 evaluator (merged, warehouse-agnostic).

This single file combines:
  * the original driver plumbing from `eva_stage2_sf.py`
    (results.log parsing, per-table query+CSV cache, stage2.json reporting) —
    with all warehouse access delegated to `db_connectors.get_connector`,
    so the same logic runs against snowflake, databricks, or redshift, and
  * the refined column comparator from `eva_stage2_sf_refined.py`
    (numeric coercion + relative/absolute tolerance + NaN-aware compare),

so there is no monkey-patching and no dependency between modules.

What the refined comparator fixes
---------------------------------
Snowflake returns NUMBER columns as Python `decimal.Decimal`. After
`df.to_csv` they serialize as `0E-9`, `29324.840000000`, `-8.5150`, etc.;
`pd.read_csv` then infers `object`, and the original element-wise comparator
fell into its `a != b` branch (`"0E-9" != "0.0"` -> Unmatched) even though
the values are numerically equal. The refined comparator coerces whole
columns to numeric before comparing and uses `np.isclose` with both relative
and absolute tolerance. It also correctly rejects NaN-vs-value rows, which
the original silently treated as matches (`NaN > x` is always False).

Usage
-----
    python eva_stage2_new.py --folder <name> --db_type databricks \
        [--database elt_claude_v5] [--gt_folder gt_v5_databricks] \
        [--credential ./databricks_credential.json]
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
# db_connectors is imported lazily inside evaluate_stage2 so the
# comparator (check_corretness) can be reused without any warehouse
# driver installed.


def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


# --------------------------------------------------------------------------
# Unique-key lookup (from sort_key.json) + key-aware row sorting
# --------------------------------------------------------------------------
# sort_key.json maps {db: {table: [key columns]}} and is the source of truth
# for each table's unique key. Before comparing, both the ground-truth and
# candidate CSVs are re-sorted by these keys so the comparison no longer
# depends on the (fragile) ORDER BY row order produced by each query.
_SORT_KEY_CANDIDATES = ["./sort_key.json", "sort_key.json"]
SORT_KEY_PATH = next((p for p in _SORT_KEY_CANDIDATES if os.path.exists(p)),
                     "./sort_key.json")


def load_sort_keys(path: str = None) -> dict:
    """Load the {db: {table: [key columns]}} map from sort_key.json."""
    path = path or SORT_KEY_PATH
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# Loaded once at import; sort keys are static for a run.
SORT_KEYS = load_sort_keys()


def table_keys(db: str, table: str) -> list:
    """Unique-key columns for one table, looked up from sort_key.json."""
    return list(SORT_KEYS.get(db, {}).get(table, []))


def _sort_series_key(col: pd.Series) -> pd.Series:
    """Build a type-consistent sort key for one column.

    Numeric-coerce when every non-null value parses cleanly (so `1389` and
    `1389.0000000000` collapse to the same value); otherwise compare as
    trimmed, lower-cased strings. NaNs are preserved so na_position applies.
    """
    num = pd.to_numeric(col, errors="coerce")
    n_non_null = col.notna().sum()
    if n_non_null > 0 and int(num.notna().sum()) == int(n_non_null):
        return num
    return col.astype("string").str.strip().str.lower()


def sort_by_keys(df: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Return df sorted by `keys` (resolved case-insensitively), with every
    remaining column appended as a deterministic tie-breaker. Sort keys are
    type-coerced so format-only differences don't change the ordering."""
    if df is None or df.empty:
        return df.reset_index(drop=True) if df is not None else df

    lower = {c.lower(): c for c in df.columns}
    resolved = []
    for k in keys:
        actual = lower.get(k.lower())
        if actual is not None and actual not in resolved:
            resolved.append(actual)
    # keys first, then everything else as tie-breakers -> fully deterministic
    ordered_cols = resolved + [c for c in df.columns if c not in resolved]
    if not ordered_cols:
        return df.reset_index(drop=True)

    aux = pd.DataFrame({c: _sort_series_key(df[c]) for c in ordered_cols})
    order = aux.sort_values(by=ordered_cols, kind="mergesort",
                            na_position="last").index
    return df.loc[order].reset_index(drop=True)


# --------------------------------------------------------------------------
# Refined column comparator (from eva_stage2_sf_refined.py)
# --------------------------------------------------------------------------
def _to_numeric_if_possible(s: pd.Series) -> pd.Series:
    """Try numeric coercion; return original Series if any non-null fails."""
    coerced = pd.to_numeric(s, errors="coerce")
    # accept only if every original non-null value parsed successfully
    if coerced.isna().sum() == s.isna().sum():
        return coerced
    return s


def _vectors_match(v1: pd.Series, v2: pd.Series, rtol: float = 1e-2,
                   atol: float = 1e-9) -> bool:
    if len(v1) != len(v2):
        return False

    # Best-effort: if BOTH sides parse cleanly as numeric, compare numerically.
    n1 = _to_numeric_if_possible(v1.reset_index(drop=True))
    n2 = _to_numeric_if_possible(v2.reset_index(drop=True))
    both_numeric = pd.api.types.is_numeric_dtype(n1) and pd.api.types.is_numeric_dtype(n2)

    if both_numeric:
        a = n1.to_numpy(dtype=float)
        b = n2.to_numpy(dtype=float)
        # element-wise: NaN==NaN ok; else within relative + absolute tolerance.
        nan_match = np.isnan(a) & np.isnan(b)
        close = np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=False)
        return bool(np.all(nan_match | close))

    # Mixed / non-numeric: case-insensitive string compare with NaN tolerance.
    for a, b in zip(v1, v2):
        if pd.isna(a) and pd.isna(b):
            continue
        if pd.isna(a) or pd.isna(b):
            return False
        if isinstance(a, str) and isinstance(b, str):
            if a.strip().lower() != b.strip().lower():
                return False
        else:
            if a != b:
                return False
    return True


def check_corretness(df_gt: pd.DataFrame, df: pd.DataFrame) -> dict:
    """Compare each gold column against its (case-insensitively matched)
    actual column. Returns a structured result dict:

        {
          "status": "ok",
          "match": <bool>,          # True iff nothing unmatched/missed
          "matched": [...],
          "unmatched": [...],
          "missed": [...],
        }
    """
    matched_cols, unmatched_cols, missed_cols = [], [], []
    df_cols_lower = {c.lower(): c for c in df.columns}

    for gold_col in df_gt.columns:
        actual_col = df_cols_lower.get(gold_col.lower())
        if actual_col is None:
            missed_cols.append(gold_col)
            continue
        if _vectors_match(df_gt[gold_col], df[actual_col]):
            matched_cols.append(gold_col)
        else:
            unmatched_cols.append(gold_col)

    return {
        "status": "ok",
        "match": not unmatched_cols and not missed_cols,
        "matched": matched_cols,
        "unmatched": unmatched_cols,
        "missed": missed_cols,
    }


# --------------------------------------------------------------------------
# Driver (from eva_stage2_sf.py)
# --------------------------------------------------------------------------
def evaluate_stage2(folder, connector, database="elt", gt_folder="gt_snowflake"):
    """`connector` is a db_connectors.BaseConnector (snowflake / databricks /
    redshift); all warehouse access goes through it. Schemas that stage 1
    marked 'Skipped:' or 'Error:' are not evaluated (Success lines only)."""
    schemas = []
    with open(f'./agent_results/{folder}/results.log', 'r') as f:
        for line in f:
            s = line.split(' ')
            if s[0] == 'Success:':
                schemas.append(s[1])
    # NOTE: the original eva_stage2_sf.py hard-coded `schemas = ['donor']`
    # here, overriding the results.log parsing above. That was a debug
    # override; left commented so full evaluation runs over all schemas.
    # schemas = ['donor']

    gt_root = (
        gt_folder
        if os.path.isabs(gt_folder)
        else os.path.join("./agent_results", gt_folder)
    )

    results = {}
    out_path = f'./agent_results/{folder}/stage2.json'

    def flush():
        # Rewrite the full JSON after every table so a crash mid-run still
        # leaves a valid, up-to-date file.
        with open(out_path, 'w') as f:
            json.dump(results, f, indent=2)

    for schema in schemas:
        # Tables to evaluate = the ground-truth tables for this schema. (The
        # original eva_sql/ query directory was empty/unavailable, so the table
        # list is driven from the GT CSVs instead.)
        gt_schema_dir = os.path.join(gt_root, schema)
        if not os.path.isdir(gt_schema_dir):
            continue
        tables = [f.name for f in os.scandir(gt_schema_dir) if f.is_file() and f.name.endswith('.csv')]
        results.setdefault(schema, {})

        for table in tables:
            table = table.split('.')[0]
            try:
                if not os.path.exists(f'./agent_results/{folder}/{schema}/{table}.csv'):
                    # Evaluation SQL uses a warehouse-neutral schema.table
                    # layout. The connector maps that logical name to the
                    # warehouse's physical namespace before execution.
                    sql_path = f'./sql/{schema}/{table}.sql'
                    if os.path.exists(sql_path):
                        with open(sql_path, 'r') as f:
                            query = f.read()
                        df = connector.query_evaluation_sql(query, database)
                    else:
                        df = connector.fetch_table(database, schema, table)
                    os.makedirs(f'./agent_results/{folder}/{schema}', exist_ok=True)
                    df.to_csv(f'./agent_results/{folder}/{schema}/{table}.csv', index=False)
                # Read BOTH sides from the materialized CSV as strings. This makes
                # the comparison deterministic and independent of how pandas would
                # infer dtypes for a freshly-fetched dataframe vs a re-read file
                # (the source of the movies_4 fetch-vs-CSV inconsistency, and of
                # int-vs-float `5`/`5.0` style flukes). check_corretness still
                # numeric-coerces columns and compares with rtol=1e-2, so numbers
                # (5 vs 5.0, 33.333333 vs 33.33333333) still match within tolerance.
                df = pd.read_csv(f'./agent_results/{folder}/{schema}/{table}.csv',
                                 dtype=str, keep_default_na=True)
                df_gt = pd.read_csv(os.path.join(gt_schema_dir, f"{table}.csv"),
                                    dtype=str, keep_default_na=True)
                # Re-sort both sides by the table's unique key before compare,
                # so the result no longer depends on the query's row order.
                keys = table_keys(schema, table)
                df_gt = sort_by_keys(df_gt, keys)
                df = sort_by_keys(df, keys)
                res = check_corretness(df_gt, df)
                res['sort_keys'] = keys
                results[schema][table] = res
            except Exception as e:
                results[schema][table] = {"status": "error", "error": str(e)}
            flush()

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage2 evaluator (warehouse-agnostic driver + "
                    "refined 0E-N decimal-aware comparator).")
    parser.add_argument("--folder", required=True,
                        help="agent_results subfolder containing results.log")
    parser.add_argument("--db_type", default="snowflake",
                        choices=["snowflake", "databricks", "redshift"])
    parser.add_argument("--database", default="elt",
                        help="Database/catalog holding the agent's task schemas")
    parser.add_argument("--gt_folder", default="gt_snowflake",
                        help="agent_results subfolder holding the ground-truth CSVs "
                             "(default: gt_snowflake)")
    parser.add_argument("--credential", default="./snowflake_credential.json",
                        help="Path to JSON credential for the chosen db_type")
    args = parser.parse_args()

    from db_connectors import get_connector
    connector = get_connector(args.db_type, read_json(args.credential))
    try:
        evaluate_stage2(args.folder, connector, args.database, args.gt_folder)
    finally:
        connector.close()
