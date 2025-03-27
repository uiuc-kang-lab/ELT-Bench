import yaml
import json
import os
import shutil

databases = [f.name for f in os.scandir('../elt-bench') if f.is_dir()]
databases.sort()

for db in databases:
  os.makedirs('../inputs',exist_ok=True)
  directory_path = f'../inputs/{db}'
  if os.path.exists(directory_path) and os.path.isdir(directory_path):
        shutil.rmtree(directory_path)
  os.system(f"cp -r ../elt-bench/{db} ../inputs")
  with open(f'../inputs/{db}/config.yaml', 'r') as file:
    config_data = yaml.safe_load(file)


  with open('./destination/snowflake_credential.json', 'r') as file:
    snowflake_credential = json.load(file)
  with open('./airbyte/airbyte_credential.json', 'r') as file:
    airbyte_credential = json.load(file)


  config_data['snowflake']['config']['account'] = snowflake_credential['account']
  config_data['Airbyte']['config']['password'] = airbyte_credential['password']
  config_data['Airbyte']['config']['username'] = airbyte_credential['username']
  config_data['Airbyte']['config']['workspace_id'] = airbyte_credential['workspace_id']
  if 'custom_api' in config_data:
    config_data['Airbyte']['config']['custom_api_definition_id'] = "8c0df240-cb31-4e3f-a98c-d64d2d846cb8"

  with open(f'../inputs/{db}/config.yaml', 'w') as file:
    yaml.dump(config_data, file)

  new_sf_credentials = {}
  new_sf_credentials['account'] = snowflake_credential['account']
  new_sf_credentials['user'] = "AIRBYTE_USER"
  new_sf_credentials['password'] = "Snowflake@123"

  with open(f'../inputs/{db}/snowflake_credential.json', 'w') as file:
    json.dump(new_sf_credentials, file)

  os.system(f"cp -r ../documentation ../inputs/{db}/")
  os.system(f"cp  ./check_job_status.py ../inputs/{db}/")
  os.system(f"mkdir ../inputs/{db}/elt")
  os.system(f"cp  ./main.tf ../inputs/{db}/elt")