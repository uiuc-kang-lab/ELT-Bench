"""Stage-1 (extract & load) evaluator.

Checks, for every task schema, that the expected raw source tables exist in
the target warehouse with the expected row counts (from table.json), and
writes Success/Error lines to agent_results/<folder>/results.log — the file
stage 2 uses to decide which schemas to evaluate.

All warehouse access goes through db_connectors.get_connector, so the same
logic runs against snowflake, databricks, or redshift.

Usage:
    python eva_stage1.py --folder claude_v5_databricks \
        --db_type databricks --database elt_claude_v5 \
        --credential ./databricks_credential.json \
        [--table_json ./table.json] [--only db1,db2] [--skip_missing_schema]
"""

import argparse
import json
import os

from db_connectors import get_connector


def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def write_message(message, log_file):
    with open(log_file, 'a') as f:
        f.write(message + '\n')


def evaluate_stage1(folder, database, connector, table_list, schemas,
                    skip_missing_schema=False):
  log_file = f'./agent_results/{folder}/results.log'
  os.makedirs(os.path.dirname(log_file), exist_ok=True)

  for schema in schemas:
      success_tables = []
      incorrect_size_tables = []
      not_found_tables = []
      tables = table_list[schema]
      if not connector.verify_schema(database, schema):
        if skip_missing_schema:
          write_message(f"Skipped: {schema} schema not found in {database}", log_file)
          print(f"{schema} (skipped: schema not found)")
          continue
        for tab in tables.keys():
          not_found_tables.append(tab)
      else:
        table_names = tables.keys()
        db_tables = {connector._norm(t) for t in connector.list_tables(database, schema)}
        for table in table_names:
          if connector._norm(table) not in db_tables:
            not_found_tables.append(table)
          else:
            size = connector.table_size(database, schema, table)
            if size != tables[table]:
              incorrect_size_tables.append(table)
              write_message(f"{schema}.{table} has {size} rows, expected {tables[table]} rows", log_file)
      if len(not_found_tables) == 0 and len(incorrect_size_tables) == 0:
        for tab in tables.keys():
          success_tables.append(tab)
        write_message(f"Success: {schema} schema and tables verified. Success tables: {success_tables}", log_file)
      else:
        for tab in tables.keys():
          if tab not in not_found_tables and tab not in incorrect_size_tables:
            success_tables.append(tab)
        write_message(f"Error: {schema} Successful table: {success_tables}  Not_found_table: {not_found_tables}, Incorrect_size_tables: {incorrect_size_tables}", log_file)
      print(schema)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage-1 (EL) evaluator.")
    parser.add_argument("--folder", required=True,
                        help="agent_results subfolder to write results.log into")
    parser.add_argument("--db_type", default="snowflake",
                        choices=["snowflake", "databricks", "redshift"])
    parser.add_argument("--database", default="elt",
                        help="Target database/catalog holding the task schemas")
    parser.add_argument("--credential", default="./snowflake_credential.json",
                        help="Path to JSON credential for the chosen db_type")
    parser.add_argument("--table_json", default="./table.json",
                        help="Expected raw-table row counts per schema")
    parser.add_argument("--only", default="",
                        help="Comma-separated schemas to check (default: all in table.json)")
    parser.add_argument("--skip_missing_schema", action="store_true",
                        help="Write 'Skipped:' instead of 'Error:' when a schema "
                             "does not exist in the target database")
    args = parser.parse_args()

    table_list = read_json(args.table_json)
    schemas = sorted(table_list.keys())
    if args.only:
        wanted = set(args.only.split(","))
        schemas = [s for s in schemas if s in wanted]

    connector = get_connector(args.db_type, read_json(args.credential))
    try:
        evaluate_stage1(args.folder, args.database, connector, table_list,
                        schemas, skip_missing_schema=args.skip_missing_schema)
    finally:
        connector.close()
