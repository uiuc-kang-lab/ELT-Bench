import snowflake.connector
import json
import os
import sys

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def write_message(message, log_file):
    with open(log_file, 'a') as f:
        f.write(message + '\n')


def check_table_size(db, table, snowflake_config):
    conn = snowflake.connector.connect(**snowflake_config)
    cursor = conn.cursor()
    eva_query = f"select count(*) from {db}.airbyte_schema.{table};"
    cursor.execute(eva_query)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result[0][0]


def verify_schema(db, snowflake_config):
  conn = snowflake.connector.connect(**snowflake_config)
  cursor = conn.cursor()
  eva_query = f"SELECT schema_name FROM {db}.information_schema.schemata;"
  cursor.execute(eva_query)
  result = cursor.fetchall()
  cursor.close()
  conn.close()
  schemas = [x[0] for x in result]
  return 'AIRBYTE_SCHEMA' in schemas


def verify_tables(db, snowflake_config):
  conn = snowflake.connector.connect(**snowflake_config)
  cursor = conn.cursor()
  eva_query = f"SELECT table_name FROM {db}.information_schema.tables WHERE table_schema = 'AIRBYTE_SCHEMA' AND table_type = 'BASE TABLE';"
  cursor.execute(eva_query)
  result = cursor.fetchall()
  cursor.close()
  conn.close()
  tables = [x[0] for x in result]
  return tables


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


def evaluate_stage1(folder, snowflake_config, example_index=None):
  log_file = f'../data/results/{folder}/stage1.log'
  with open('./table.json', 'r') as f:
      table_list = json.load(f)

  databases = [f.name for f in os.scandir('../tasks') if f.is_dir()]
  databases.sort()
  databases = filter_databases(databases, example_index)

  print(f"\n{'='*60}")
  print(f"STAGE 1: Table Verification")
  print(f"{'='*60}")
  print(f"Evaluating {len(databases)} database(s)...\n")

  for idx, db in enumerate(databases, 1):
      print(f"[{idx}/{len(databases)}] Evaluating tables for database: {db}")
      success_tables = []
      incorrect_size_tables = []
      not_found_tables = []
      tables = table_list[db]
      if not verify_schema(db, snowflake_config):
        print(f"    Schema 'AIRBYTE_SCHEMA' not found")
        for tab in tables.keys():
          not_found_tables.append(tab)
      else:
        print(f"    Schema verified, checking {len(tables)} table(s)...")
        table_names = tables.keys()
        sf_tables = verify_tables(db, snowflake_config)
        for table in table_names:
          if table.upper() not in sf_tables:
            not_found_tables.append(table)
          else:
            size = check_table_size(db, table, snowflake_config)
            if size != tables[table]:
              incorrect_size_tables.append(table)
              write_message(f"{db}.{table} has {size} rows, expected {tables[table]} rows", log_file)
      if len(not_found_tables) == 0 and len(incorrect_size_tables) == 0:
        for tab in tables.keys():
          success_tables.append(tab)
        write_message(f"Success: {db} schema and tables verified. Success tables: {success_tables}", log_file)
        print(f"    Result: SUCCESS - {len(success_tables)} table(s) verified")
      else:
        for tab in tables.keys():
          if tab not in not_found_tables and tab not in incorrect_size_tables:
            success_tables.append(tab)
        write_message(f"Error: {db} Successful table: {success_tables}  Not_found_table: {not_found_tables}, Incorrect_size_tables: {incorrect_size_tables}", log_file)
        print(f"    Result: FAILED - Success: {len(success_tables)}, Not found: {len(not_found_tables)}, Wrong size: {len(incorrect_size_tables)}")

  print(f"\nStage 1 complete. Log written to: {log_file}")
