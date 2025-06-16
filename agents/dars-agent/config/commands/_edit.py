#!/root/miniconda3/envs/aider/bin/python

# @yaml
# signature: edit $<to_replace> $<new_content>
# docstring: Replaces occurrence of $<to_replace> with $<new_content> in the currently open file.
# arguments:
#   to_replace:
#       type: string
#       description: The text to be replaced in the file.
#       required: true
#   new_content:
#       type: string
#       description: The new text to replace with.
#       required: true

import os
import sys
import shutil
import argparse
import warnings
from pathlib import Path
from datetime import datetime
from _agent_skills import edit_file_by_replace

# Suppress any future warnings if necessary
warnings.simplefilter("ignore", category=FutureWarning)

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

    os.environ['ENABLE_AUTO_LINT'] = 'true'

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Edit a file by replacing specific content based on diffs.'
    )
    parser.add_argument('to_replace', type=str, help='The text to be replaced in the file.')
    parser.add_argument('new_content', type=str, help='The new text to replace with.')
    args = parser.parse_args()

    to_replace = args.to_replace
    new_content = args.new_content

    # Validate arguments
    if not to_replace:
        print("Error: 'to_replace' must not be empty.")
        print("Usage: edit $<to_replace> $<new_content>")
        sys.exit(1)
    if to_replace == new_content:
        print("Error: 'to_replace' and 'new_content' must be different.")
        print("Usage: edit $<to_replace> $<new_content>")
        sys.exit(1)

    # Create backup before editing
    create_backup(current_file)

    # Call the edit function
    try:
        edit_file_by_replace(current_file, to_replace, new_content)
    except Exception as e:
        print(f"Error editing file: {e}", file=sys.stderr)
        print("Usage: edit $<to_replace> $<new_content>")
        sys.exit(1)

if __name__ == '__main__':
    main()