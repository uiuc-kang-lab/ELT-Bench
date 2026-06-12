#!/usr/bin/env python3
"""
Main Data Loader for ELT-Bench-Verified

Orchestrates loading data into all source systems:
- PostgreSQL databases
- MongoDB collections
- S3 buckets (LocalStack)

Usage:
    python load_all.py [--task TASK_NAME]

Examples:
    python load_all.py                      # Load all tasks
    python load_all.py --task address       # Load single task
    python load_all.py --task address,movie # Load specific tasks
"""

import argparse
import os
import subprocess
import sys


def run_loader(script_name, task=None):
    """Run a loader script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, script_name)

    cmd = [sys.executable, script_path]
    if task:
        cmd.extend(["--task", task])

    result = subprocess.run(cmd, cwd=script_dir)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Load all data for ELT-Bench tasks")
    parser.add_argument("--task", type=str, help="Specific task(s) to load (comma-separated)")
    parser.add_argument("--skip-postgres", action="store_true", help="Skip PostgreSQL loading")
    parser.add_argument("--skip-s3", action="store_true", help="Skip S3 loading")
    parser.add_argument("--skip-mongodb", action="store_true", help="Skip MongoDB loading")
    args = parser.parse_args()

    print("=" * 60)
    print("  ELT-Bench Data Loader")
    print("=" * 60)
    print()

    success = True

    # Load PostgreSQL
    if not args.skip_postgres:
        print("\n[1/3] Loading PostgreSQL databases...")
        print("-" * 60)
        if not run_loader("postgres_loader.py", args.task):
            print("WARNING: PostgreSQL loading had failures")
            success = False
    else:
        print("\n[1/3] Skipping PostgreSQL (--skip-postgres)")

    # Load S3
    if not args.skip_s3:
        print("\n[2/3] Loading S3 buckets...")
        print("-" * 60)
        if not run_loader("s3_loader.py", args.task):
            print("WARNING: S3 loading had failures")
            success = False
    else:
        print("\n[2/3] Skipping S3 (--skip-s3)")

    # Load MongoDB
    if not args.skip_mongodb:
        print("\n[3/3] Loading MongoDB collections...")
        print("-" * 60)
        if not run_loader("mongodb_loader.py", args.task):
            print("WARNING: MongoDB loading had failures")
            success = False
    else:
        print("\n[3/3] Skipping MongoDB (--skip-mongodb)")

    print()
    print("=" * 60)
    if success:
        print("  All data loaded successfully!")
    else:
        print("  Data loading completed with some warnings")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
