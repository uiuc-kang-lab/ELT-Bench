import yaml
import json
import os
import shutil
import csv
import glob


def uppercase_csv_files(directory):
    """
    Convert all CSV file contents (column names in schemas) to uppercase
    to avoid Snowflake case sensitivity issues.
    """
    csv_files = glob.glob(os.path.join(directory, '**', '*.csv'), recursive=True)

    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)

            if len(rows) > 0:
                # Convert column names (first column of each row after header) to uppercase
                # This handles schema files where first column is the column name
                rows[1:] = [[row[0].upper()] + row[1:] if row else row for row in rows[1:]]

                with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)

        except Exception as e:
            print(f"  Warning: Error processing {csv_file}: {e}")

        # Rename file to uppercase
        file_dir = os.path.dirname(csv_file)
        file_name = os.path.basename(csv_file)
        new_file_name = file_name.upper()

        if file_name != new_file_name:
            new_file_path = os.path.join(file_dir, new_file_name)
            try:
                os.rename(csv_file, new_file_path)
            except Exception as e:
                print(f"  Warning: Error renaming {csv_file}: {e}")


def uppercase_data_model_yaml(yaml_file_path):
    """
    Convert all model names and column names in data_model.yaml to uppercase
    to match Snowflake case conventions.
    """
    if not os.path.exists(yaml_file_path):
        return

    try:
        with open(yaml_file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if data and 'models' in data:
            for model in data['models']:
                # Convert model name to uppercase
                if 'name' in model:
                    model['name'] = model['name'].upper()

                # Convert column names to uppercase
                if 'columns' in model:
                    for column in model['columns']:
                        if 'name' in column:
                            column['name'] = column['name'].upper()

        with open(yaml_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=float('inf'))

    except Exception as e:
        print(f"  Warning: Error processing {yaml_file_path}: {e}")


def uppercase_config_yaml(yaml_file_path):
    """
    Convert snowflake database name in config.yaml to uppercase
    to match Snowflake case conventions.
    """
    if not os.path.exists(yaml_file_path):
        return

    try:
        with open(yaml_file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if data and 'snowflake' in data:
            if 'config' in data['snowflake'] and 'database' in data['snowflake']['config']:
                data['snowflake']['config']['database'] = data['snowflake']['config']['database'].upper()

        with open(yaml_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=float('inf'))

    except Exception as e:
        print(f"  Warning: Error processing {yaml_file_path}: {e}")


def main():
    print("Generating agent workspaces...")

    # Get list of benchmark databases
    databases = [f.name for f in os.scandir('../tasks') if f.is_dir()]
    databases.sort()

    print(f"  Found {len(databases)} benchmark problems")

    # Load credentials
    try:
        with open('./destination/snowflake_credential.json', 'r') as file:
            snowflake_credential = json.load(file)
    except FileNotFoundError:
        print("ERROR: setup/destination/snowflake_credential.json not found")
        print("       Please create this file with your Snowflake credentials.")
        return

    try:
        with open('./airbyte/airbyte_credential.json', 'r') as file:
            airbyte_credential = json.load(file)
    except FileNotFoundError:
        print("ERROR: setup/airbyte/airbyte_credential.json not found")
        print("       Please create this file with your Airbyte credentials.")
        return

    # Process each database
    for i, db in enumerate(databases):
        print(f"  [{i+1}/{len(databases)}] Processing {db}...")

        # Create output directory
        os.makedirs('../data/inputs', exist_ok=True)
        directory_path = f'../data/inputs/{db}'

        # Remove existing directory if present
        if os.path.exists(directory_path) and os.path.isdir(directory_path):
            shutil.rmtree(directory_path)

        # Copy benchmark definition
        os.system(f"cp -r ../tasks/{db} ../data/inputs")

        # Apply uppercase normalization for Snowflake compatibility
        uppercase_csv_files(directory_path)
        uppercase_data_model_yaml(f'../data/inputs/{db}/data_model.yaml')
        uppercase_config_yaml(f'../data/inputs/{db}/config.yaml')

        # Load and update config
        with open(f'../data/inputs/{db}/config.yaml', 'r') as file:
            config_data = yaml.safe_load(file)

        # Inject Snowflake credentials
        config_data['snowflake']['config']['account'] = snowflake_credential['account']
        config_data['snowflake']['config']['password'] = snowflake_credential['password']
        config_data['snowflake']['config']['role'] = snowflake_credential['role']
        config_data['snowflake']['config']['username'] = snowflake_credential['user']
        config_data['snowflake']['config']['warehouse'] = snowflake_credential['warehouse']

        # Inject Airbyte credentials
        config_data['Airbyte']['config']['password'] = airbyte_credential['password']
        config_data['Airbyte']['config']['username'] = airbyte_credential['username']
        config_data['Airbyte']['config']['workspace_id'] = airbyte_credential['workspace_id']

        if 'custom_api' in config_data:
            config_data['Airbyte']['config']['custom_api_definition_id'] = airbyte_credential['api_definition_id']

        # Write updated config
        with open(f'../data/inputs/{db}/config.yaml', 'w') as file:
            yaml.dump(config_data, file)

        # Create simplified snowflake credentials file for agent use
        new_sf_credentials = {
            'account': snowflake_credential['account'],
            'user': snowflake_credential['user'],
            'password': snowflake_credential['password']
        }

        with open(f'../data/inputs/{db}/snowflake_credential.json', 'w') as file:
            json.dump(new_sf_credentials, file, indent=2)

        # Copy agent reference documentation
        os.system(f"cp -r workspace_files/documentation ../data/inputs/{db}/")

        # Copy job status checker
        os.system(f"cp ./workspace_files/check_job_status.py ../data/inputs/{db}/")

        # Create Terraform directory with main.tf
        os.makedirs(f'../data/inputs/{db}/elt', exist_ok=True)
        os.system(f"cp ./workspace_files/main.tf ../data/inputs/{db}/elt")

    print("")
    print(f"  Successfully generated {len(databases)} agent workspaces")
    print(f"  Output directory: data/inputs/")


if __name__ == "__main__":
    main()
