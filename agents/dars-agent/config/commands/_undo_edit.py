#!/root/miniconda3/envs/aider/bin/python

# @yaml
# signature: undo_edit [file_path]
# docstring: Reverts the last edit made to the specified file. If no file is provided, reverts the last edit on the currently open file.
# arguments:
#   file_path:
#     type: string
#     description: The path to the file to undo the last edit for.
#     required: false

import os
import sys
import warnings
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

# Suppress any future warnings if necessary
warnings.simplefilter("ignore", category=FutureWarning)

# Configuration
BACKUP_DIR = '/root/tmp/file_edit_backups'
BACKUP_HISTORY_FILE = os.path.join(BACKUP_DIR, 'backup_history.txt')

class BackupManager:
    @staticmethod
    def get_file_backups(file_path: str) -> List[Tuple[str, str]]:
        """Get all backups for a specific file."""
        if not os.path.exists(BACKUP_HISTORY_FILE):
            return []

        backups = []
        with open(BACKUP_HISTORY_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        backup_path, orig_path = line.strip().split("::")
                        if orig_path == file_path and os.path.exists(backup_path):
                            backups.append((backup_path, orig_path))
                    except ValueError:
                        continue
        return backups

    @staticmethod
    def restore_backup(backup_path: str, target_file: str) -> bool:
        """Restore a file from its backup."""
        try:
            if not os.path.exists(backup_path):
                return False
            shutil.copy2(backup_path, target_file)
            return True
        except Exception:
            return False

    @staticmethod
    def update_history(entries: List[str]) -> None:
        """Update the backup history file."""
        with open(BACKUP_HISTORY_FILE, 'w') as f:
            f.writelines(entries)

    @staticmethod
    def cleanup_old_backups(file_path: str, keep_last: int = 5) -> None:
        """Remove old backups keeping only the specified number of recent ones."""
        backups = BackupManager.get_file_backups(file_path)
        if len(backups) <= keep_last:
            return

        # Remove older backups
        for backup_path, _ in backups[:-keep_last]:
            try:
                os.remove(backup_path)
            except OSError:
                pass

def undo_last_edit(file_path: str) -> bool:
    """
    Undo the last edit for a specific file.
    Returns True if successful, False otherwise.
    """
    try:
        # Get all backups for the file
        backups = BackupManager.get_file_backups(file_path)
        if not backups:
            print(f"No edits have been made to the file: {file_path}")
            return False

        # Get the most recent backup
        last_backup, original_file = backups[-1]

        # Verify files exist
        if not os.path.exists(last_backup):
            print(f"Backup file not found: {last_backup}")
            return False

        if not os.path.exists(original_file):
            print(f"Original file not found: {original_file}")
            return False

        # Restore from backup
        if not BackupManager.restore_backup(last_backup, original_file):
            print("Failed to restore from backup")
            return False

        # Update backup history
        with open(BACKUP_HISTORY_FILE, 'r') as f:
            all_entries = f.readlines()
        
        entries_to_keep = [
            entry for entry in all_entries 
            if entry.strip() != f"{last_backup}::{original_file}"
        ]
        
        BackupManager.update_history(entries_to_keep)

        # Cleanup old backups
        BackupManager.cleanup_old_backups(file_path)

        print(f"Successfully restored {file_path} to previous version")
        return True

    except Exception as e:
        print(f"Error during undo operation: {e}", file=sys.stderr)
        return False

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Reverts the last edit made to the specified file.'
    )
    parser.add_argument('file_path', nargs='?', default=None, 
                       help='The path to the file to undo the last edit for.')
    args = parser.parse_args()

    # Determine the file to undo
    file_path = args.file_path
    if not file_path:
        file_path = os.environ.get('CURRENT_FILE')
        if not file_path:
            print('No file specified and no file open. Use the `open` command first or specify a file.')
            sys.exit(1)

    # Attempt to undo last edit
    if not undo_last_edit(file_path):
        sys.exit(1)

if __name__ == '__main__':
    main()