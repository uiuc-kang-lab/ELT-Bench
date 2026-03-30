import requests
import base64
import json
import argparse
import time
import sys

server = "airbyte-abctl-control-plane:80/api/public/v1"

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--username", type=str, required=True, help="Username")
parser.add_argument("--password", type=str, required=True, help="Password")
parser.add_argument("--wait", action="store_true", help="Wait until all jobs complete (not running)")
parser.add_argument("--timeout", type=int, default=300, help="Max wait time in seconds (default: 300)")
parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds (default: 30)")
args = parser.parse_args()

username = args.username
password = args.password

# Read connection IDs from tfstate
connectionid_list = []
try:
    with open('/workspace/elt/terraform.tfstate', 'r', encoding='utf-8') as f:
        tfstate_data = json.load(f)
    for resource in tfstate_data['resources']:
        if resource['type'] == 'airbyte_connection':
            connectionid_list.append(resource['instances'][0]['attributes']['connection_id'])
except Exception as e:
    print(f"Error reading .tfstate file: {e}")
    sys.exit(1)

if not connectionid_list:
    print("No Airbyte connections found in tfstate.")
    sys.exit(1)

# Prepare authentication headers
auth_string = f"{username}:{password}"
auth_bytes = auth_string.encode("utf-8")
auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

headers = {
    "Authorization": f"Basic {auth_base64}",
    "accept": "application/json"
}

def get_job_statuses():
    """Fetch and return job statuses for our connections."""
    url = f"http://{server}/jobs?limit=100000"
    response = requests.get(url, headers=headers)
    parsed_response = json.loads(response.text)
    jobs_data = parsed_response.get('data', [])

    # Get latest job for each connection
    connection_jobs = {}
    for job in jobs_data:
        conn_id = job['connectionId']
        if conn_id in connectionid_list:
            # Keep the most recent job (highest jobId) for each connection
            if conn_id not in connection_jobs or job['jobId'] > connection_jobs[conn_id]['jobId']:
                connection_jobs[conn_id] = job

    return connection_jobs

def print_statuses(connection_jobs):
    """Print job statuses."""
    for conn_id, job in connection_jobs.items():
        print(f"Job {job['jobId']}: Connection {conn_id}, Status: {job['status']}")

def all_complete(connection_jobs):
    """Check if all jobs are complete (not running/pending)."""
    if len(connection_jobs) < len(connectionid_list):
        return False  # Some connections don't have jobs yet

    running_statuses = {'running', 'pending', 'incomplete'}
    for job in connection_jobs.values():
        if job['status'].lower() in running_statuses:
            return False
    return True

# Main logic
if args.wait:
    # Wait mode: poll until all jobs complete or timeout
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        if elapsed > args.timeout:
            print(f"\nTimeout after {args.timeout}s. Some jobs may still be running.")
            connection_jobs = get_job_statuses()
            print_statuses(connection_jobs)
            sys.exit(1)

        connection_jobs = get_job_statuses()

        if all_complete(connection_jobs):
            print("All jobs completed:")
            print_statuses(connection_jobs)

            # Check for failures
            failed = [j for j in connection_jobs.values() if j['status'].lower() == 'failed']
            if failed:
                print(f"\nWARNING: {len(failed)} job(s) failed!")
                sys.exit(1)
            else:
                print("\nAll jobs succeeded!")
                sys.exit(0)

        # Still running, wait and retry
        time.sleep(args.interval)
else:
    # Default mode: just print current statuses
    connection_jobs = get_job_statuses()
    print_statuses(connection_jobs)
