#!/usr/bin/env python3
"""
PostgreSQL Database Loader

Loads data into PostgreSQL databases for all tasks.
Reads schema definitions from setup/schemas/*.sql and data from data/source/db/.

Usage:
    python postgres_loader.py [--task TASK_NAME] [--data-dir PATH]

Examples:
    python postgres_loader.py                      # Load all tasks
    python postgres_loader.py --task address       # Load single task
    python postgres_loader.py --task address,movie # Load specific tasks
"""

import argparse
import os
import subprocess
import sys
import yaml


# PostgreSQL connection settings
PG_HOST = "localhost"
PG_PORT = "5433"
PG_USER = "postgres"
PG_PASSWORD = "testelt"


def run_psql(command, database=None):
    """Execute a psql command."""
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD

    cmd = ["psql", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER]
    if database:
        cmd.extend(["-d", database])
    cmd.extend(["-c", command])

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def run_psql_file(filepath, database):
    """Execute a SQL file via psql."""
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD

    cmd = ["psql", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER, "-d", database, "-f", filepath]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def copy_csv_to_table(database, table, csv_path):
    """Load CSV data into a table using COPY."""
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD

    copy_cmd = f"\\COPY {table} FROM '{csv_path}' DELIMITER ',' CSV HEADER;"
    cmd = ["psql", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER, "-d", database, "-c", copy_cmd]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def get_tasks_with_postgres(tasks_dir):
    """Get list of tasks that have PostgreSQL sources."""
    tasks = []
    for task_name in sorted(os.listdir(tasks_dir)):
        config_path = os.path.join(tasks_dir, task_name, 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            if config and 'postgres' in config:
                tables = config['postgres'].get('config', {}).get('tables', [])
                if tables:
                    tasks.append((task_name, tables))
    return tasks


def load_task(task_name, tables, schemas_dir, data_dir):
    """Load a single task's PostgreSQL data."""
    print(f"\n{'='*60}")
    print(f"Loading task: {task_name}")
    print(f"{'='*60}")

    # Check for schema file
    schema_file = os.path.join(schemas_dir, f'{task_name}.sql')
    if not os.path.exists(schema_file):
        print(f"  ERROR: No schema file found at {schema_file}")
        return False

    # Create database
    print(f"  Creating database '{task_name}'...")
    run_psql(f"DROP DATABASE IF EXISTS {task_name};")
    success, _, err = run_psql(f"CREATE DATABASE {task_name};")
    if not success:
        print(f"  ERROR: Failed to create database: {err}")
        return False

    # Load schema
    print(f"  Loading schema from {schema_file}...")
    success, _, err = run_psql_file(schema_file, task_name)
    if not success:
        print(f"  ERROR: Failed to load schema: {err}")
        return False

    # Load data for each table
    task_data_dir = os.path.join(data_dir, task_name)
    for table in tables:
        csv_path = os.path.join(task_data_dir, f'{table}.csv')
        if os.path.exists(csv_path):
            print(f"  Loading table '{table}' from {csv_path}...")
            success, _, err = copy_csv_to_table(task_name, table, os.path.abspath(csv_path))
            if not success:
                print(f"    WARNING: Failed to load {table}: {err}")
        else:
            print(f"  WARNING: Data file not found: {csv_path}")

    print(f"  Done: {task_name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Load PostgreSQL databases for ELT-Bench tasks")
    parser.add_argument("--task", type=str, help="Specific task(s) to load (comma-separated)")
    parser.add_argument("--data-dir", type=str, default="../../data/source/db",
                       help="Path to data directory")
    parser.add_argument("--schemas-dir", type=str, default="../schemas",
                       help="Path to schemas directory")
    parser.add_argument("--tasks-dir", type=str, default="../../tasks",
                       help="Path to tasks directory")
    args = parser.parse_args()

    # Resolve paths relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, args.data_dir)
    schemas_dir = os.path.join(script_dir, args.schemas_dir)
    tasks_dir = os.path.join(script_dir, args.tasks_dir)

    print("PostgreSQL Database Loader")
    print(f"  Data directory: {data_dir}")
    print(f"  Schemas directory: {schemas_dir}")
    print(f"  Tasks directory: {tasks_dir}")

    # Get all tasks with PostgreSQL sources
    all_tasks = get_tasks_with_postgres(tasks_dir)
    print(f"\nFound {len(all_tasks)} tasks with PostgreSQL sources")

    # Filter tasks if specified
    if args.task:
        task_filter = set(args.task.split(','))
        all_tasks = [(name, tables) for name, tables in all_tasks if name in task_filter]
        print(f"Filtered to {len(all_tasks)} tasks: {[t[0] for t in all_tasks]}")

    # Load each task
    success_count = 0
    fail_count = 0

    for task_name, tables in all_tasks:
        if load_task(task_name, tables, schemas_dir, data_dir):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed")
    print(f"{'='*60}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
