import os 
import json
database = ['retails']
for db in database:
  with open(f'./{db}/main.tf') as file:
    content = file.read()
  with open('../setup/airbyte/airbyte_credential.json') as file:
    content1 = json.load(file)
  with open('../setup/destination/snowflake_credential.json') as file:
    content2 = json.load(file)
  content = content.replace('<username>', content1['username']).replace('<password>', content1['password'])
  content = content.replace('<workspace_id>', content1['workspace_id']).replace('<custom_api_definition_id>', content1['api_definition_id'])
  content = content.replace('<snowflake_host>', f'{content2["account"]}.snowflakecomputing.com')
  content = content.replace('airbyte-abctl-control-plane:80', 'localhost:8000')
  os.makedirs(f'./{db}',exist_ok=True)
  with open(f'./{db}/main.tf','w') as f:
    f.write(content)