import requests
import base64
import json
import time
import argparse


def get_connections(server, headers):
  connectionid_list = []
  try:
      with open('/workspace/elt/terraform.tfstate', 'r', encoding='utf-8') as f:
          tfstate_data = json.load(f)
      for resource in tfstate_data['resources']:
        if resource['type'] == 'airbyte_connection':
          connectionid_list.append(resource['instances'][0]['attributes']['connection_id'])
      return connectionid_list
  except Exception as e:
      print(f"Error reading .tfstate file: {e}")
      return connectionid_list


def get_job_status(server, headers):
  connectionid_list = get_connections(server, headers) 
  if not connectionid_list:
    print('Connection not found')
    return
  url = f"http://{server}/api/public/v1/jobs?limit=100000"
  successful_jobs = []
  failed_jobs = []
  # Process jobs
  while True:
    all_completed = True
    response = requests.get(url, headers=headers)
    parsed_response = json.loads(response.text)
    parsed_response = parsed_response['data']
    for job in parsed_response:
      if job['connectionId'] not in connectionid_list:
        continue
      if job['status'] == 'succeeded':
        if job['connectionId'] not in successful_jobs:
          successful_jobs.append(job['connectionId'])
      elif job['status'] == 'failed':
        if job['connectionId'] not in failed_jobs:
          failed_jobs.append(job['connectionId'])
      else:
        all_completed = False
    if all_completed:
      break
    time.sleep(10)
  print("The connection id of successful jobs are: ", successful_jobs)
  print("The connection id of failed jobs are: ", failed_jobs)

if __name__ == "__main__":
  arg = argparse.ArgumentParser()
  arg.add_argument("--server", type=str, help="Server address" , required=True)
  arg.add_argument("--username", type=str, help="Username", required=True)
  arg.add_argument("--password", type=str, help="Password", required=True)
  args = arg.parse_args()
  server = args.server
  auth_string = f"{args.username}:{args.password}"
  auth_bytes = auth_string.encode("utf-8")
  auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

  headers = {
      "Authorization": f"Basic {auth_base64}",
      "accept": "application/json"
  }
  get_job_status(server, headers)

  
