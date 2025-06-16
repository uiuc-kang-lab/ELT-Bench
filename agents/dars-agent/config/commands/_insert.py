#!/root/miniconda3/envs/aider/bin/python

# @yaml
# signature: insert <line_number> $<content>
# docstring: Inserts $<content> at the given <line_number> in the currently open file.
# arguments:
#   line_number:
#       type: int
#       description: The line number where the content should be inserted.
#       required: true
#   content:
#       type: string
#       description: The content to insert at the specified line number.
#       required: true

import os
import re
import sys
import shutil
import argparse
import warnings
from pathlib import Path
from datetime import datetime

# Suppress any future warnings if necessary
warnings.simplefilter("ignore", category=FutureWarning)

from _agent_skills import insert_content_at_line

# Configuration
BACKUP_DIR = '/root/tmp/file_edit_backups'
BACKUP_HISTORY_FILE = os.path.join(BACKUP_DIR, 'backup_history.txt')

def create_backup(file_path):
    """Create a backup of the file before editing."""
    try:
        # Create backup directory if it doesn't exist
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
        
        # Create backup history file if it doesn't exist
        if not os.path.exists(BACKUP_HISTORY_FILE):
            Path(BACKUP_HISTORY_FILE).touch()
            
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{Path(file_path).stem}_{timestamp}{Path(file_path).suffix}"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # Create backup
        shutil.copy2(file_path, backup_path)
        
        # Record backup in history file
        with open(BACKUP_HISTORY_FILE, 'a') as f:
            f.write(f"{backup_path}::{file_path}\n")
            
    except Exception as e:
        print(f"Warning: Failed to create backup: {e}", file=sys.stderr)

def main():
    # Check if CURRENT_FILE environment variable is set
    current_file = os.environ.get('CURRENT_FILE')
    if not current_file:
        print('No file open. Use the `open` command first.')
        sys.exit(1)

    # Set ENABLE_AUTO_LINT environment variable
    os.environ['ENABLE_AUTO_LINT'] = 'true'

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Inserts $<content> at the given <line_number> in the currently open file.'
    )
    parser.add_argument('line_number', type=int, help='The line number where the content should be inserted.')
    parser.add_argument('content', type=str, help='The content to insert at the specified line number.')
    args = parser.parse_args()

    line_number = args.line_number
    content = args.content

    # Validate arguments
    if line_number <= 0:
        print("Error: 'line_number' must be a valid integer.")
        print("Usage: insert <line_number> $<content>")
        sys.exit(1)
    if not content:
        print("Error: 'content' must not be empty.")
        print("Usage: insert <line_number> $<content>")
        sys.exit(1)

    # Create backup before editing
    create_backup(current_file)

    # Call the insert function
    try:
        insert_content_at_line(current_file, line_number, content)
    except Exception as e:
        print(f"Error inserting content: {e}", file=sys.stderr)
        print("Usage: insert <line_number> $<content>")
        sys.exit(1)

if __name__ == '__main__':
    main()
