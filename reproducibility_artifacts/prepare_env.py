#!/usr/bin/env python3
"""
prepare_env.py -- Generate per-database debugging workspaces from stage2.log.

Reads stage2.log, identifies databases with unmatched columns, and builds
a workspace for each one with the following structure:

    {DATABASE}/
    ├── data_model.yaml
    ├── gt/
    │   └── {TABLE}.csv
    ├── predicted/
    │   └── {TABLE}.csv
    │   └── {TABLE}.sql
    ├── source_schemas/
    │   └── *.csv
    └── source_tables/
        └── *.csv / *.jsonl / *.parquet
"""

import os
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    requests = None


# ─────────────────────────────────────────────
# Paths (relative to project root)
# ─────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR / ".." / ".."
PROJECT_ROOT = PROJECT_ROOT.resolve()

STAGE2_LOG = SCRIPT_DIR / "stage2.log"
OUTPUT_DIR = SCRIPT_DIR / ".." / "workspaces"
OUTPUT_DIR = OUTPUT_DIR.resolve()

INPUTS_DIR = PROJECT_ROOT / "inputs"
SETUP_DATA_DIR = PROJECT_ROOT / "setup" / "data"
REST_API_DATA_DIR = PROJECT_ROOT / "elt-docker" / "rest_api" / "data"
GT_DIR = PROJECT_ROOT / "evaluation" / "gt"
AGENT_RESULTS_DIR = (
    PROJECT_ROOT / "evaluation" / "agent_results"
    / "SWE-agent_claude-sonnet-4-5-function-calling"
)
TRAJ_ROOT = (
    PROJECT_ROOT / "agents" / "SWE-agent-v1.1.0" / "trajectories" / "chz"
)
TRAJ_TEMPLATE = (
    "no_config__openai--aws--claude-sonnet-4-5__t-0.00__p-None__c-0.00___{db}"
)


# ─────────────────────────────────────────────
# 1. Parse stage2.log
# ─────────────────────────────────────────────
def parse_stage2_log(log_path: Path) -> dict[str, list[str]]:
    """
    Returns {db_name: [table_1, table_2, ...]} for databases that have
    at least one unmatched column.
    """
    databases: dict[str, list[str]] = {}
    current_db = None
    current_table = None

    with open(log_path, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("Database:"):
                current_db = line.replace("Database:", "").strip()
                current_table = None
                continue

            if line.startswith("Table:"):
                current_table = line.replace("Table:", "").strip()
                continue

            if line.startswith("Unmatched columns:"):
                if current_db is None or current_table is None:
                    continue
                cols = re.findall(r"'([^']+)'", line)
                if cols:
                    databases.setdefault(current_db, []).append(current_table)

    return databases


# ─────────────────────────────────────────────
# 2. Extract SQL from patch files
# ─────────────────────────────────────────────
def extract_sql_from_patch(patch_path: Path) -> dict[str, str]:
    """Parse a unified diff patch and return {model_name: sql_content}."""
    models = {}
    current_model = None
    collecting = False
    buffer = []

    with open(patch_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.startswith("diff --git"):
                if current_model and buffer:
                    models[current_model] = "\n".join(buffer).strip()
                current_model = None
                collecting = False
                buffer = []
                continue

            if "models/" in line and line.endswith(".sql"):
                current_model = Path(line.split("models/")[-1]).stem
                continue

            if line.startswith("@@"):
                collecting = True
                continue

            if not collecting or current_model is None:
                continue

            if line.startswith("+++ ") or line.startswith("--- "):
                continue

            if line.startswith("+") and not line.startswith("++"):
                buffer.append(line[1:])

        if current_model and buffer:
            models[current_model] = "\n".join(buffer).strip()

    return models


# ─────────────────────────────────────────────
# 3. Download flat files from config.yaml
# ─────────────────────────────────────────────
def download_flat_files(db_name: str, dest_dir: Path) -> None:
    """Download flat files listed in inputs/{db}/config.yaml."""
    if yaml is None or requests is None:
        return

    config_path = INPUTS_DIR / db_name / "config.yaml"
    if not config_path.exists():
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    flat_files = config.get("flat_files", None)
    if not flat_files:
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    for entry in flat_files:
        url = entry.get("path", "")
        table_name = entry.get("table", "")
        file_format = entry.get("format", "csv")

        if not url or not table_name:
            continue

        output_path = dest_dir / f"{table_name}.{file_format}"
        if output_path.exists():
            continue

        print(f"    Downloading flat file {table_name} ...")
        try:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"    [WARN] Failed to download {table_name}: {e}")


# ─────────────────────────────────────────────
# 4. Build workspace for one database
# ─────────────────────────────────────────────
def build_workspace(db_name: str, tables: list[str]) -> None:
    ws = OUTPUT_DIR / db_name
    ws.mkdir(parents=True, exist_ok=True)

    # ── data_model.yaml ──
    dm_src = INPUTS_DIR / db_name / "data_model.yaml"
    if dm_src.exists():
        shutil.copy2(dm_src, ws / "data_model.yaml")
    else:
        print(f"  [WARN] Missing data_model.yaml")

    # ── source_schemas/ ──
    schemas_src = INPUTS_DIR / db_name / "schemas"
    if schemas_src.exists():
        shutil.copytree(schemas_src, ws / "source_schemas", dirs_exist_ok=True)
    else:
        print(f"  [WARN] Missing schemas/")

    # ── source_tables/ (three sources) ──
    st_dest = ws / "source_tables"
    st_dest.mkdir(parents=True, exist_ok=True)

    # a) setup/data/{DB}
    setup_src = SETUP_DATA_DIR / db_name
    if setup_src.exists():
        shutil.copytree(setup_src, st_dest, dirs_exist_ok=True)

    # b) elt-docker/rest_api/data/{DB}
    rest_src = REST_API_DATA_DIR / db_name
    if rest_src.exists():
        for item in rest_src.iterdir():
            dest_item = st_dest / item.name
            if item.is_file():
                shutil.copy2(item, dest_item)
            elif item.is_dir() and not dest_item.exists():
                shutil.copytree(item, dest_item)

    # c) flat files from config.yaml
    download_flat_files(db_name, st_dest)

    # ── predicted/ (SQL from patch + CSV from agent_results) ──
    pred_dir = ws / "predicted"
    pred_dir.mkdir(parents=True, exist_ok=True)

    # Extract SQL from patch
    traj_dir = TRAJ_ROOT / TRAJ_TEMPLATE.format(db=db_name) / db_name
    patch_file = traj_dir / f"{db_name}.patch"

    sql_models: dict[str, str] = {}
    if patch_file.exists():
        sql_models = extract_sql_from_patch(patch_file)
        for model_name, sql in sql_models.items():
            (pred_dir / f"{model_name}.sql").write_text(sql, encoding="utf-8")
    else:
        print(f"  [WARN] Missing patch file: {patch_file}")

    # Copy predicted CSVs (only for tables that have an extracted SQL)
    agent_db_dir = AGENT_RESULTS_DIR / db_name
    if agent_db_dir.exists():
        sql_basenames = set(sql_models.keys())
        for csv_file in agent_db_dir.iterdir():
            if csv_file.suffix == ".csv" and csv_file.stem in sql_basenames:
                shutil.copy2(csv_file, pred_dir / csv_file.name)
    else:
        print(f"  [WARN] Missing agent_results/{db_name}")

    # ── gt/ ──
    gt_dest = ws / "gt"
    gt_dest.mkdir(parents=True, exist_ok=True)

    gt_src = GT_DIR / db_name
    if gt_src.exists():
        sql_basenames = set(sql_models.keys())
        for table_name in sql_basenames:
            csv_src = gt_src / f"{table_name}.csv"
            if csv_src.exists():
                shutil.copy2(csv_src, gt_dest / f"{table_name}.csv")
            else:
                print(f"  [WARN] Missing GT CSV: {table_name}.csv")
    else:
        print(f"  [WARN] Missing evaluation/gt/{db_name}")


# ─────────────────────────────────────────────
# 5. Validate workspace
# ─────────────────────────────────────────────
def validate_workspace(db_name: str) -> list[str]:
    """Return a list of issues found in the workspace."""
    ws = OUTPUT_DIR / db_name
    issues = []

    if not (ws / "data_model.yaml").exists():
        issues.append("missing data_model.yaml")

    for subdir in ("gt", "predicted", "source_schemas", "source_tables"):
        d = ws / subdir
        if not d.exists() or not any(d.iterdir()):
            issues.append(f"empty or missing {subdir}/")

    # Check predicted has matching .sql and .csv pairs
    pred = ws / "predicted"
    if pred.exists():
        sqls = {f.stem for f in pred.glob("*.sql")}
        csvs = {f.stem for f in pred.glob("*.csv")}
        missing_csv = sqls - csvs
        if missing_csv:
            issues.append(f"predicted/ SQL without CSV: {missing_csv}")

    # Check gt has CSVs matching predicted SQLs
    gt = ws / "gt"
    if pred.exists() and gt.exists():
        sqls = {f.stem for f in pred.glob("*.sql")}
        gt_csvs = {f.stem for f in gt.glob("*.csv")}
        missing_gt = sqls - gt_csvs
        if missing_gt:
            issues.append(f"gt/ missing CSV for: {missing_gt}")

    return issues


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    if not STAGE2_LOG.exists():
        print(f"Error: stage2.log not found at {STAGE2_LOG}")
        sys.exit(1)

    print(f"Parsing {STAGE2_LOG} ...")
    db_tables = parse_stage2_log(STAGE2_LOG)
    print(f"Found {len(db_tables)} databases with unmatched columns\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for db_name in sorted(db_tables):
        tables = db_tables[db_name]
        print(f">> {db_name} ({len(tables)} tables with unmatched cols)")
        build_workspace(db_name, tables)

    # Validation
    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)

    all_ok = True
    for db_name in sorted(db_tables):
        issues = validate_workspace(db_name)
        if issues:
            all_ok = False
            print(f"\n[WARN] {db_name}:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"  [OK] {db_name}")

    if all_ok:
        print("\nAll workspaces validated successfully")
    else:
        print("\nSome workspaces have issues (see above)")

    print(f"\nOutput: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
