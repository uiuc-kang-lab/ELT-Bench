import argparse
import json
import os
from pathlib import Path


EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVALUATION_DIR.parent


def read_json(path):
    with Path(path).open("r") as file:
        return json.load(file)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run warehouse-agnostic ELT-Bench evaluation."
    )
    parser.add_argument(
        "--folder",
        required=True,
        help="Name of the result folder under evaluation/agent_results",
    )
    parser.add_argument(
        "--db-type",
        choices=("snowflake", "databricks", "redshift"),
        default="snowflake",
        help="Destination warehouse (default: snowflake)",
    )
    parser.add_argument(
        "--database",
        default="elt",
        help=(
            "Databricks catalog containing task schemas. The value is ignored "
            "for the current Snowflake and Redshift layouts."
        ),
    )
    parser.add_argument(
        "--credential",
        type=Path,
        help="Destination credential JSON (defaults to setup/destination/<db-type>_credential.json)",
    )
    parser.add_argument(
        "--table-json",
        type=Path,
        default=EVALUATION_DIR / "table.json",
        help="Expected source-table row counts",
    )
    parser.add_argument(
        "--gt-folder",
        type=Path,
        help=(
            "Ground-truth CSV directory. Relative paths are resolved below "
            "evaluation/agent_results; defaults to gt_<db-type>."
        ),
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated task schemas to evaluate",
    )
    parser.add_argument(
        "--skip-missing-schema",
        action="store_true",
        help="Skip rather than fail schemas that do not exist",
    )
    parser.add_argument(
        "--stage",
        choices=("all", "1", "2"),
        default="all",
        help="Run both stages or only one stage (default: all)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    credential_path = args.credential or (
        PROJECT_DIR / "setup/destination" / f"{args.db_type}_credential.json"
    )
    credential_path = credential_path.resolve()
    table_json_path = args.table_json.resolve()
    gt_folder = args.gt_folder or Path(f"gt_{args.db_type}")
    if not gt_folder.is_absolute():
        gt_folder = EVALUATION_DIR / "agent_results" / gt_folder

    # The imported evaluators intentionally write below ./agent_results.
    os.chdir(EVALUATION_DIR)
    from db_connectors import get_connector
    from eva_stage1 import evaluate_stage1
    from eva_stage2 import evaluate_stage2

    table_list = read_json(table_json_path)
    schemas = sorted(table_list)
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        schemas = [schema for schema in schemas if schema in wanted]

    result_directory = EVALUATION_DIR / "agent_results" / args.folder
    result_directory.mkdir(parents=True, exist_ok=True)
    results_log = result_directory / "results.log"

    connector = get_connector(args.db_type, read_json(credential_path))
    try:
        if args.stage in ("all", "1"):
            # Stage 1 appends as it progresses; start each requested run cleanly.
            results_log.unlink(missing_ok=True)
            evaluate_stage1(
                args.folder,
                args.database,
                connector,
                table_list,
                schemas,
                skip_missing_schema=args.skip_missing_schema,
            )

        if args.stage in ("all", "2"):
            if not results_log.is_file():
                raise FileNotFoundError(
                    f"Stage 1 results do not exist: {results_log}"
                )
            if not gt_folder.is_dir():
                raise FileNotFoundError(
                    f"Ground-truth CSV directory does not exist: {gt_folder}"
                )
            evaluate_stage2(
                args.folder,
                connector,
                database=args.database,
                gt_folder=str(gt_folder),
            )
    finally:
        connector.close()


if __name__ == "__main__":
    main()
