import snowflake.connector
import json
import argparse

# Snowflake connection details
with open('../setup/destination/snowflake_credential.json') as file:
    SNOWFLAKE_CONFIG = json.load(file)
ROLE = "AIRBYTE_ROLE"

def create_database(database_name):
    try:
        # Establish connection
        conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
        cursor = conn.cursor()
        create_db_query = f"drop DATABASE IF EXISTS {database_name};"
        
        # Execute the query
        cursor.execute(create_db_query)
        print(f"Database '{database_name}' dropped successfully.")
        # SQL to create a new database
        create_db_query = f"CREATE DATABASE IF NOT EXISTS {database_name};"
        
        # Execute the query
        cursor.execute(create_db_query)
        print(f"Database '{database_name}' created successfully.")
        grant_query = f"GRANT OWNERSHIP ON DATABASE {database_name} TO ROLE AIRBYTE_ROLE;"
        cursor.execute(grant_query)
        print(f"Role '{ROLE}' granted OWNERSHIP on database '{database_name}' successfully.")


    except snowflake.connector.errors.ProgrammingError as e:
        print(f"Error: {e}")
    
    finally:
        # Close cursor and connection
        cursor.close()
        conn.close()

if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--db", type=str, help="database", required=True)
    args = arg.parse_args()
    db = args.db

    create_database(db.upper())