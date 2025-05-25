import json 
import base64
import requests
import argparse

if __name__ == "__main__":
  arg = argparse.ArgumentParser()
  arg.add_argument("--db", type=str, help="database", required=True)
  args = arg.parse_args()

  db = args.db
  with open('../setup/airbyte/airbyte_credential.json') as file:
    content = json.load(file)
  username = content['username']
  password = content['password']
  auth_string = f"{username}:{password}"
  auth_bytes = auth_string.encode("utf-8")
  auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")


  headers = {"Authorization": f"Basic {auth_base64}",
            "accept": "application/json"
            }
  with open(f'./{db}/terraform.tfstate','r') as f:
    data =json.load(f)

  connection_ids = []
  for item in data['resources']:
    if item['type'] == 'airbyte_connection':
      for tt in item['instances']:
        connection_ids.append(tt['attributes']['connection_id'])

  url = f"http://localhost:8000/api/public/v1/jobs"
  for c_id in connection_ids:
    payload = {
        "jobType": "sync",
        "connectionId": c_id
    }
    response = requests.post(url, json=payload, headers=headers)
    print(response.text)