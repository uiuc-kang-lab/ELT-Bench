import snowflake.connector
import json
import os

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


def evaluate_stage1(folder, snowflake_config):
  log_file = f'./agent_results/{folder}/results.log'
  with open('./table.json', 'r') as f:
      table_list = json.load(f)

  databases = [f.name for f in os.scandir('../elt-bench') if f.is_dir()]
  databases.sort()

  for db in databases:
      success_tables = []
      incorrect_size_tables = []
      not_found_tables = []
      tables = table_list[db]
      if not verify_schema(db, snowflake_config):
        for tab in tables.keys():
          not_found_tables.append(tab)
      else:
        table_names = tables.keys()
        sf_tables = verify_tables(db, snowflake_config)
        all_found = True
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
      else:
        for tab in tables.keys():
          if tab not in not_found_tables and tab not in incorrect_size_tables:
            success_tables.append(tab)
        write_message(f"Error: {db} Successful table: {success_tables}  Not_found_table: {not_found_tables}, Incorrect_size_tables: {incorrect_size_tables}", log_file)
      print(db)
