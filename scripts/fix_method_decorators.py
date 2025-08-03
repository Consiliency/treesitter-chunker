#!/usr/bin/env python3
"""Fix @staticmethod and @classmethod decorator issues.

This script fixes:
1. @staticmethod methods that have 'self' parameter
2. @classmethod methods that have 'self' instead of 'cls'
3. Methods that could be @staticmethod (don't use self)
"""

import ast
import os
from pathlib import Path


class MethodDecoratorFixer(ast.NodeTransformer):
    """AST transformer to fix method decorator issues."""

    def __init__(self):
        self.changes_made = []
        self.current_class = None
        self.methods_using_self = set()
        self.methods_using_cls = set()

    def visit_ClassDef(self, node):
        """Track current class context."""
        old_class = self.current_class
        self.current_class = node

        # First pass: analyze which methods use self/cls
        analyzer = MethodAnalyzer()
        analyzer.visit(node)
        self.methods_using_self = analyzer.methods_using_self
        self.methods_using_cls = analyzer.methods_using_cls

        # Second pass: fix decorators
        self.generic_visit(node)

        self.current_class = old_class
        return node

    def visit_FunctionDef(self, node):
        """Fix method decorator issues."""
        if not self.current_class:
            return self.generic_visit(node)

        # Check decorators
        is_staticmethod = any(
            isinstance(dec, ast.Name) and dec.id == "staticmethod"
            for dec in node.decorator_list
        )
        is_classmethod = any(
            isinstance(dec, ast.Name) and dec.id == "classmethod"
            for dec in node.decorator_list
        )

        # Get first parameter name
        first_param = None
        if node.args.args:
            first_param = node.args.args[0].arg

        # Fix @staticmethod with self
        if is_staticmethod and first_param == "self":
            # Remove self parameter
            node.args.args = node.args.args[1:]
            self.changes_made.append(
                f"Removed 'self' from @staticmethod {node.name}",
            )

        # Fix @classmethod with self instead of cls
        elif is_classmethod and first_param == "self":
            # Rename self to cls
            node.args.args[0].arg = "cls"
            # Update all references in the method body
            renamer = VariableRenamer("self", "cls")
            for stmt in node.body:
                renamer.visit(stmt)
            self.changes_made.append(
                f"Renamed 'self' to 'cls' in @classmethod {node.name}",
            )

        # Check if method could be @staticmethod
        elif not is_staticmethod and not is_classmethod and first_param == "self":
            method_key = f"{self.current_class.name}.{node.name}"
            if method_key not in self.methods_using_self and method_key not in self.methods_using_cls:
                # Add @staticmethod decorator
                node.decorator_list.insert(0, ast.Name(id="staticmethod", ctx=ast.Load()))
                # Remove self parameter
                node.args.args = node.args.args[1:]
                self.changes_made.append(
                    f"Added @staticmethod to {node.name} (doesn't use self)",
                )

        return self.generic_visit(node)


class MethodAnalyzer(ast.NodeVisitor):
    """Analyze which methods use self or cls."""

    def __init__(self):
        self.methods_using_self = set()
        self.methods_using_cls = set()
        self.current_class = None
        self.current_method = None
        self.first_param = None

    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        if not self.current_class:
            return

        old_method = self.current_method
        old_param = self.first_param

        self.current_method = node.name
        if node.args.args:
            self.first_param = node.args.args[0].arg
        else:
            self.first_param = None

        # Check if method uses self or cls
        for stmt in node.body:
            self.visit(stmt)

        self.current_method = old_method
        self.first_param = old_param

    def visit_Name(self, node):
        if not self.current_class or not self.current_method:
            return

        method_key = f"{self.current_class}.{self.current_method}"

        if isinstance(node.ctx, ast.Load):
            if node.id == "self" and self.first_param == "self":
                self.methods_using_self.add(method_key)
            elif node.id == "cls" and self.first_param in ("self", "cls"):
                self.methods_using_cls.add(method_key)

    def visit_Attribute(self, node):
        if not self.current_class or not self.current_method:
            self.generic_visit(node)
            return

        method_key = f"{self.current_class}.{self.current_method}"

        if isinstance(node.value, ast.Name):
            if node.value.id == "self" and self.first_param == "self":
                self.methods_using_self.add(method_key)
            elif node.value.id == "cls" and self.first_param in ("self", "cls"):
                self.methods_using_cls.add(method_key)

        self.generic_visit(node)


class VariableRenamer(ast.NodeTransformer):
    """Rename variables in AST."""

    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name

    def visit_Name(self, node):
        if node.id == self.old_name:
            node.id = self.new_name
        return node


def fix_file(file_path: Path) -> list[str]:
    """Fix method decorator issues in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    fixer = MethodDecoratorFixer()
    new_tree = fixer.visit(tree)

    if fixer.changes_made:
        # Convert AST back to code
        try:
            import astor
            new_code = astor.to_source(new_tree)
        except ImportError:
            # Fallback to ast.unparse (Python 3.9+)
            new_code = ast.unparse(new_tree)

        file_path.write_text(new_code, encoding="utf-8")
        return fixer.changes_made

    return []


def main():
    """Main function."""
    # Find all Python files in the project
    project_root = Path(__file__).parent.parent

    # Directories to exclude
    exclude_dirs = {
        ".venv", "venv", "build", "dist", ".git", "ide",
        "node_modules", "grammars", "__pycache__", ".mypy_cache",
        ".ruff_cache", ".pytest_cache", "egg-info",
    }

    python_files = []
    for root, dirs, files in os.walk(project_root):
        # Remove excluded directories from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                # Additional check for egg-info in path
                if "egg-info" not in str(file_path):
                    python_files.append(file_path)

    print(f"Found {len(python_files)} Python files to check")

    total_changes = []
    files_changed = 0

    for file_path in python_files:
        changes = fix_file(file_path)
        if changes:
            files_changed += 1
            total_changes.extend(changes)
            print(f"\n{file_path}:")
            for change in changes:
                print(f"  - {change}")

    print("\n\nSummary:")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {len(total_changes)}")

    # Show change type breakdown
    change_types = {}
    for change in total_changes:
        if "Removed 'self' from @staticmethod" in change:
            key = "Removed self from @staticmethod"
        elif "Renamed 'self' to 'cls'" in change:
            key = "Renamed self to cls in @classmethod"
        elif "Added @staticmethod" in change:
            key = "Added @staticmethod to methods not using self"
        else:
            key = "Other"
        change_types[key] = change_types.get(key, 0) + 1

    print("\nChanges by type:")
    for change_type, count in sorted(change_types.items(), key=lambda x: -x[1]):
        print(f"  - {change_type}: {count}")


if __name__ == "__main__":
    main()
