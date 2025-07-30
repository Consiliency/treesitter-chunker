#!/usr/bin/env python3
"""Fix A001 and A002 errors by renaming variables that shadow builtins."""

import ast
import re
from pathlib import Path

# Common builtins that are often shadowed
COMMON_BUILTINS = {
    "format": "fmt",
    "type": "type_",
    "id": "id_",
    "file": "file_path",
    "dir": "directory",
    "next": "next_item",
    "filter": "filter_func",
    "map": "map_func",
    "sum": "total",
    "min": "minimum",
    "max": "maximum",
    "list": "items",
    "dict": "mapping",
    "set": "unique_items",
    "str": "text",
    "int": "number",
    "float": "decimal",
    "bool": "flag",
    "bytes": "data",
    "input": "user_input",
    "open": "file_open",
    "range": "span",
    "len": "length",
    "all": "all_items",
    "any": "any_item",
    "help": "help_text",
    "hash": "hash_value",
    "object": "obj",
    "property": "prop",
}


class BuiltinShadowFixer(ast.NodeVisitor):
    """AST visitor to find and fix builtin shadows."""

    def __init__(self):
        self.shadows = []  # List of (line, col, old_name, new_name, is_arg)
        self.local_vars = set()  # Track local variables to avoid false positives

    def visit_FunctionDef(self, node):
        """Visit function definition."""
        # Check function arguments
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.arg in COMMON_BUILTINS:
                new_name = COMMON_BUILTINS[arg.arg]
                self.shadows.append(
                    (arg.lineno, arg.col_offset, arg.arg, new_name, True),
                )

        # Save current local vars
        old_locals = self.local_vars.copy()

        # Visit function body
        self.generic_visit(node)

        # Restore local vars
        self.local_vars = old_locals

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        """Visit assignment."""
        # Check for variable assignments
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in COMMON_BUILTINS and target.id not in self.local_vars:
                    new_name = COMMON_BUILTINS[target.id]
                    self.shadows.append(
                        (target.lineno, target.col_offset, target.id, new_name, False),
                    )
                self.local_vars.add(target.id)

        self.generic_visit(node)

    def visit_For(self, node):
        """Visit for loop."""
        # Check loop variable
        if isinstance(node.target, ast.Name):
            if node.target.id in COMMON_BUILTINS:
                new_name = COMMON_BUILTINS[node.target.id]
                self.shadows.append(
                    (
                        node.target.lineno,
                        node.target.col_offset,
                        node.target.id,
                        new_name,
                        False,
                    ),
                )
            self.local_vars.add(node.target.id)

        self.generic_visit(node)

    def visit_comprehension(self, node):
        """Visit comprehension."""
        # Check comprehension variable
        if isinstance(node.target, ast.Name):
            if node.target.id in COMMON_BUILTINS:
                new_name = COMMON_BUILTINS[node.target.id]
                self.shadows.append(
                    (
                        node.target.lineno,
                        node.target.col_offset,
                        node.target.id,
                        new_name,
                        False,
                    ),
                )

        self.generic_visit(node)


def fix_file(file_path: Path) -> bool:
    """Fix builtin shadowing in a file."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            content = f.read()

        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            print(f"Syntax error in {file_path}, skipping")
            return False

        # Find shadows
        fixer = BuiltinShadowFixer()
        fixer.visit(tree)

        if not fixer.shadows:
            return False

        # Apply replacements
        lines = content.splitlines(keepends=True)

        # Sort by line and column (reverse to avoid offset issues)
        fixer.shadows.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Track replacements to apply globally
        replacements = {}

        for line_no, col_offset, old_name, new_name, is_arg in fixer.shadows:
            replacements[old_name] = new_name

        # Now apply replacements throughout the file
        new_content = content

        for old_name, new_name in replacements.items():
            # Use word boundary regex to avoid partial matches
            pattern = r"\b" + re.escape(old_name) + r"\b"

            # Skip if it would replace too many things (likely false positive)
            matches = re.findall(pattern, new_content)
            if len(matches) > 50:  # Arbitrary threshold
                print(
                    f"Skipping {old_name} -> {new_name} in {file_path} (too many matches: {len(matches)})",
                )
                continue

            new_content = re.sub(pattern, new_name, new_content)

        if new_content != content:
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed {file_path}")
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return False


def main():
    """Main function."""
    # Get all Python files
    python_files = []
    for pattern in ["**/*.py"]:
        python_files.extend(Path().glob(pattern))

    # Exclude certain directories
    exclude_dirs = {
        ".git",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        ".claude",
        "grammars",
        "archive",
        "worktrees",
        "flask",
        "rust",
        "click",
        "gin",
        "guava",
        "googletest",
        "lodash",
        "ruby",
        "serde",
    }

    python_files = [
        f for f in python_files if not any(exc in f.parts for exc in exclude_dirs)
    ]

    fixed_count = 0
    for file_path in python_files:
        if fix_file(file_path):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
