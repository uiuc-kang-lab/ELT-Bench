#!/usr/bin/env python3

import os
import glob
import re
from typing import List, Set, Dict, Tuple, NamedTuple, Optional
from pathlib import Path
import ast
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class CodeChange:
    file_path: str
    class_name: Optional[str]
    function_name: Optional[str]
    changed_lines: List[str]

class ImportInfo(NamedTuple):
    module_name: str
    imported_names: Set[str]
    is_from_import: bool

class TestImpactAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.test_patterns = [
            "test_*.py",
            "*_test.py",
            "tests/**/*.py",
            "testing/**/*.py",
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/*.py",
            "**/testing/*.py",
            "**/*tests/*.py",
            "**/*_tests/*.py",
            "**/unittests/*.py",
            "**/unit_tests/*.py",
            "test/**/*.py",
        ]

    def parse_patch_content(self, patch_content: str) -> List[CodeChange]:
        """Parse a patch string to identify specific function and class changes."""
        changes = []
        current_file = None
        current_hunk = []
        changed_files = {}

        for line in patch_content.split('\n'):
            if line.startswith('diff --git'):
                if current_file and current_hunk:
                    changed_files[current_file] = current_hunk
                match = re.search(r'b/(.*?)$', line)
                if match:
                    current_file = match.group(1)
                else:
                    continue
                current_hunk = []
            elif line.startswith('+') and not line.startswith('+++'):
                current_hunk.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                current_hunk.append(line[1:])

        if current_file and current_hunk:
            changed_files[current_file] = current_hunk

        # Analyze each changed file
        for file_path, changed_lines in changed_files.items():
            if not file_path.endswith('.py'):
                continue

            try:
                file_path_obj = self.repo_path / file_path
                if not file_path_obj.exists():
                    continue

                with open(file_path_obj, 'r') as f:
                    file_content = f.read()

                tree = ast.parse(file_content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_lines = file_content.split('\n')[node.lineno-1:node.end_lineno]
                        if any(line.strip() in '\n'.join(class_lines) for line in changed_lines):
                            changes.append(CodeChange(
                                file_path=file_path,
                                class_name=node.name,
                                function_name=None,
                                changed_lines=changed_lines
                            ))
                            
                    elif isinstance(node, ast.FunctionDef):
                        func_lines = file_content.split('\n')[node.lineno-1:node.end_lineno]
                        if any(line.strip() in '\n'.join(func_lines) for line in changed_lines):
                            class_name = None
                            for parent in ast.walk(tree):
                                if isinstance(parent, ast.ClassDef) and \
                                   parent.lineno <= node.lineno and \
                                   parent.end_lineno >= node.end_lineno:
                                    class_name = parent.name
                                    break
                                    
                            changes.append(CodeChange(
                                file_path=file_path,
                                class_name=class_name,
                                function_name=node.name,
                                changed_lines=changed_lines
                            ))

            except Exception as e:
                pass

        return changes

    def analyze_imports(self, file_path: str) -> List[ImportInfo]:
        """Analyze imports in a Python file."""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append(ImportInfo(
                            module_name=name.name,
                            imported_names={name.asname or name.name},
                            is_from_import=False
                        ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(ImportInfo(
                            module_name=node.module,
                            imported_names={n.name for n in node.names},
                            is_from_import=True
                        ))
        except Exception as e:
            pass

        return imports

    def find_affected_tests(self, changes: List[CodeChange]) -> Set[str]:
        """Find tests affected by specific code changes."""
        affected_tests = set()
        
        test_files = []
        for pattern in self.test_patterns:
            pattern = pattern.replace('/', os.sep)
            matches = glob.glob(str(self.repo_path / "**" / pattern), recursive=True)
            test_files.extend(matches)

        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    test_content = f.read()
                
                imports = self.analyze_imports(test_file)
                
                for change in changes:
                    module_path = Path(change.file_path).with_suffix('')
                    module_name = str(module_path).replace(os.sep, '.')
                    
                    for imp in imports:
                        if (imp.module_name in module_name or module_name in imp.module_name):
                            if change.class_name and change.class_name in test_content:
                                relative_path = str(Path(test_file).relative_to(self.repo_path))
                                affected_tests.add(relative_path)
                                break
                            
                            if change.function_name and change.function_name in test_content:
                                tree = ast.parse(test_content)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.Call):
                                        if (isinstance(node.func, ast.Name) and 
                                            node.func.id == change.function_name) or \
                                           (isinstance(node.func, ast.Attribute) and 
                                            node.func.attr == change.function_name):
                                            relative_path = str(Path(test_file).relative_to(self.repo_path))
                                            affected_tests.add(relative_path)
                                            break
                                
            except Exception as e:
                pass

        return affected_tests

    def run_analysis(self, patches: List[str]) -> Dict[str, List]:
        """Run the complete analysis for multiple patches."""
        all_changes = []
        for patch in patches:
            changes = self.parse_patch_content(patch)
            all_changes.extend(changes)

        # Get unique changes
        unique_changes = {
            (change.file_path, change.class_name, change.function_name)
            for change in all_changes
        }

        # Find affected tests
        affected_tests = self.find_affected_tests(all_changes)

        # Prepare the results with unique entries
        formatted_changes = []
        for file_path, class_name, function_name in unique_changes:
            change_info = {"file": file_path}
            if class_name:
                change_info["class"] = class_name
            if function_name:
                change_info["function"] = function_name
            formatted_changes.append(change_info)

        return {
            "changes": formatted_changes,
            "affected_tests": sorted(list(affected_tests))
        }

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python script.py 'patch1' 'patch2' ...")
        sys.exit(1)
    
    patches = sys.argv[1:]
    analyzer = TestImpactAnalyzer(os.getcwd())
    results = analyzer.run_analysis(patches)
    
    print("\nDetected Changes:")
    print(results["changes"])
    
    print("\nTest Files:")
    print(results["affected_tests"])

if __name__ == "__main__":
    main()