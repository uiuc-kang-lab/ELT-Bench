#!/usr/bin/env python3
"""
MongoDB Data Loader

Loads data into MongoDB collections for all tasks.
Reads collection definitions from mongodb_config.json and data from data/source/db/.

Usage:
    python mongodb_loader.py [--task TASK_NAME] [--data-dir PATH]

Examples:
    python mongodb_loader.py                      # Load all tasks
    python mongodb_loader.py --task address       # Load single task
    python mongodb_loader.py --task address,movie # Load specific tasks
"""

import argparse
import json
import math
import os
import sys

import pandas as pd
from pymongo import MongoClient


# MongoDB connection settings
MONGO_HOST = "localhost"
MONGO_PORT = 27017


def get_mongo_client():
    """Create and return a MongoDB client."""
    mongo_uri = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/?directConnection=true&serverSelectionTimeoutMS=2000"
    return MongoClient(mongo_uri)


def load_task(client, db_name, tables, data_dir):
    """Load a single task's MongoDB data."""
    print(f"\n{'='*60}")
    print(f"Loading MongoDB data for task: {db_name}")
    print(f"{'='*60}")

    task_data_dir = os.path.join(data_dir, db_name)

    # Drop and recreate database
    print(f"  Dropping existing database '{db_name}'...")
    client.drop_database(db_name)
    mg_db = client[db_name]

    success = True
    for table in tables:
        csv_path = os.path.join(task_data_dir, f'{table}.csv')

        if not os.path.exists(csv_path):
            print(f"  WARNING: Data file not found: {csv_path}")
            continue

        print(f"  Loading collection '{table}' from {csv_path}...")
        try:
            df = pd.read_csv(csv_path)
            df = df.where(pd.notnull(df), None)

            collection = mg_db[table]
            data = df.to_dict(orient='records')

            # Clean data - remove None and NaN values
            cleaned_data = []
            for row in data:
                cleaned_data.append({
                    k: v for k, v in row.items()
                    if v is not None and not (isinstance(v, float) and math.isnan(float(v)))
                })

            if cleaned_data:
                collection.insert_many(cleaned_data)
                print(f"    Inserted {len(cleaned_data)} documents")
            else:
                print(f"    WARNING: No data to insert for {table}")

        except Exception as e:
            print(f"    ERROR: Failed to load {table}: {e}")
            success = False

    print(f"  Done: {db_name}")
    return success


def main():
    parser = argparse.ArgumentParser(description="Load MongoDB data for ELT-Bench tasks")
    parser.add_argument("--task", type=str, help="Specific task(s) to load (comma-separated)")
    parser.add_argument("--data-dir", type=str, default="../../data/source/db",
                       help="Path to data directory")
    parser.add_argument("--config", type=str, default="mongodb_config.json",
                       help="Path to MongoDB config file")
    args = parser.parse_args()

    # Resolve paths relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, args.data_dir)
    config_path = os.path.join(script_dir, args.config)

    print("MongoDB Data Loader")
    print(f"  Data directory: {data_dir}")
    print(f"  Config file: {config_path}")
    print(f"  Host: {MONGO_HOST}:{MONGO_PORT}")

    # Load config
    if not os.path.exists(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        return 1

    with open(config_path, 'r') as f:
        mongo_dbs = json.load(f)

    print(f"\nFound {len(mongo_dbs)} tasks with MongoDB sources")

    # Filter tasks if specified
    if args.task:
        task_filter = set(args.task.split(','))
        mongo_dbs = {k: v for k, v in mongo_dbs.items() if k in task_filter}
        print(f"Filtered to {len(mongo_dbs)} tasks: {list(mongo_dbs.keys())}")

    # Connect to MongoDB
    try:
        client = get_mongo_client()
        # Test connection
        client.admin.command('ping')
        print("  Connected to MongoDB successfully")
    except Exception as e:
        print(f"ERROR: Failed to connect to MongoDB: {e}")
        return 1

    # Load each task
    success_count = 0
    fail_count = 0

    for db_name, tables in mongo_dbs.items():
        if load_task(client, db_name, tables, data_dir):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed")
    print(f"{'='*60}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
