#!/usr/bin/env python3
"""
S3 (LocalStack) Data Loader

Uploads data files to LocalStack S3 buckets for all tasks.
Reads S3 configuration from tasks/*/config.yaml.

Usage:
    python s3_loader.py [--task TASK_NAME] [--data-dir PATH]

Examples:
    python s3_loader.py                      # Load all tasks
    python s3_loader.py --task address       # Load single task
    python s3_loader.py --task address,movie # Load specific tasks
"""

import argparse
import os
import subprocess
import sys
import yaml


# LocalStack S3 settings
AWS_ENDPOINT_URL = "http://localhost:4566"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"
AWS_REGION = "us-west-2"


def run_aws_command(args):
    """Execute an AWS CLI command against LocalStack."""
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    env["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
    env["AWS_DEFAULT_REGION"] = AWS_REGION
    env["AWS_ENDPOINT_URL"] = AWS_ENDPOINT_URL

    cmd = ["aws", "--endpoint-url", AWS_ENDPOINT_URL] + args

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def create_bucket(bucket_name):
    """Create an S3 bucket."""
    success, _, err = run_aws_command(["s3", "mb", f"s3://{bucket_name}"])
    # Ignore "bucket already exists" errors
    if not success and "BucketAlreadyOwnedByYou" not in err and "BucketAlreadyExists" not in err:
        return False, err
    return True, ""


def upload_file(local_path, s3_path):
    """Upload a file to S3."""
    success, _, err = run_aws_command(["s3", "cp", local_path, s3_path])
    return success, err


def get_tasks_with_s3(tasks_dir):
    """Get list of tasks that have S3 sources."""
    tasks = []
    for task_name in sorted(os.listdir(tasks_dir)):
        config_path = os.path.join(tasks_dir, task_name, 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            if config and 'aws_s3' in config:
                s3_data = config['aws_s3'].get('data', [])
                if s3_data:
                    tasks.append((task_name, s3_data))
    return tasks


def load_task(task_name, s3_data, data_dir):
    """Load a single task's S3 data."""
    print(f"\n{'='*60}")
    print(f"Loading S3 data for task: {task_name}")
    print(f"{'='*60}")

    task_data_dir = os.path.join(data_dir, task_name)
    bucket_name = f"{task_name.replace('_', '-')}-bucket"

    # Create bucket
    print(f"  Creating bucket '{bucket_name}'...")
    success, err = create_bucket(bucket_name)
    if not success:
        print(f"  ERROR: Failed to create bucket: {err}")
        return False

    # Upload each file
    for item in s3_data:
        s3_path = item.get('path', '')
        table_name = item.get('table', '')

        if not s3_path or not table_name:
            continue

        # Extract filename from s3 path
        # Format: s3://bucket-name/filename.jsonl
        filename = s3_path.split('/')[-1]

        # Look for the file in the data directory
        local_path = os.path.join(task_data_dir, filename)

        if os.path.exists(local_path):
            print(f"  Uploading '{filename}' to {s3_path}...")
            success, err = upload_file(local_path, s3_path)
            if not success:
                print(f"    WARNING: Failed to upload: {err}")
        else:
            print(f"  WARNING: File not found: {local_path}")

    print(f"  Done: {task_name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Load S3 data for ELT-Bench tasks")
    parser.add_argument("--task", type=str, help="Specific task(s) to load (comma-separated)")
    parser.add_argument("--data-dir", type=str, default="../../data/source/db",
                       help="Path to data directory")
    parser.add_argument("--tasks-dir", type=str, default="../../tasks",
                       help="Path to tasks directory")
    args = parser.parse_args()

    # Resolve paths relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, args.data_dir)
    tasks_dir = os.path.join(script_dir, args.tasks_dir)

    print("S3 (LocalStack) Data Loader")
    print(f"  Data directory: {data_dir}")
    print(f"  Tasks directory: {tasks_dir}")
    print(f"  Endpoint: {AWS_ENDPOINT_URL}")

    # Get all tasks with S3 sources
    all_tasks = get_tasks_with_s3(tasks_dir)
    print(f"\nFound {len(all_tasks)} tasks with S3 sources")

    # Filter tasks if specified
    if args.task:
        task_filter = set(args.task.split(','))
        all_tasks = [(name, data) for name, data in all_tasks if name in task_filter]
        print(f"Filtered to {len(all_tasks)} tasks: {[t[0] for t in all_tasks]}")

    # Load each task
    success_count = 0
    fail_count = 0

    for task_name, s3_data in all_tasks:
        if load_task(task_name, s3_data, data_dir):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed")
    print(f"{'='*60}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
