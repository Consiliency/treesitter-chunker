#!/usr/bin/env python3
"""Fix PERF401 errors - manual list comprehensions that can be simplified."""

import ast
import re
from pathlib import Path


class ListComprehensionFixer(ast.NodeTransformer):
    """AST transformer to fix manual list comprehensions."""

    def __init__(self):
        self.changes = []

    def visit_For(self, node):
        """Visit For loops and check for manual list comprehensions."""
        self.generic_visit(node)

        # Check if this is a pattern like:
        # result = []
        # for item in iterable:
        #     result.append(expr)

        # Look for append calls in the body
        if len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
            expr = node.body[0]
            if isinstance(expr.value, ast.Call):
                call = expr.value
                if (
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr == "append"
                    and len(call.args) == 1
                ):
                    # This is a candidate for list comprehension
                    self.changes.append(
                        {
                            "type": "manual_comprehension",
                            "node": node,
                            "list_name": (
                                call.func.value.id
                                if isinstance(call.func.value, ast.Name)
                                else None
                            ),
                            "target": node.target,
                            "iter": node.iter,
                            "value": call.args[0],
                        },
                    )

        return node


def fix_manual_comprehensions(file_path: Path) -> bool:
    """Fix manual list comprehensions in a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content
        content.splitlines()

        # Common patterns for manual list comprehensions
        patterns = [
            # Pattern 1: result = []\n    for x in y:\n        result.append(...)
            {
                "pattern": re.compile(
                    r"(\s*)(\w+)\s*=\s*\[\]\s*\n"
                    r"\1for\s+(\w+)\s+in\s+(.+?):\s*\n"
                    r"\1\s+\2\.append\(([^)]+)\)\s*(?:\n|$)",
                    re.MULTILINE,
                ),
                "replacement": r"\1\2 = [\5 for \3 in \4]",
            },
            # Pattern 2: list initialization followed by loop with append
            {
                "pattern": re.compile(
                    r"(\s*)(\w+)\s*=\s*\[\]\s*\n"
                    r"(\s*)for\s+(\w+)\s+in\s+(.+?):\s*\n"
                    r"\3\s+\2\.append\(([^)]+)\)\s*(?:\n|$)",
                    re.MULTILINE,
                ),
                "replacement": r"\1\2 = [\6 for \4 in \5]",
            },
            # Pattern 3: With if condition
            {
                "pattern": re.compile(
                    r"(\s*)(\w+)\s*=\s*\[\]\s*\n"
                    r"\1for\s+(\w+)\s+in\s+(.+?):\s*\n"
                    r"\1\s+if\s+(.+?):\s*\n"
                    r"\1\s+\s+\2\.append\(([^)]+)\)\s*(?:\n|$)",
                    re.MULTILINE,
                ),
                "replacement": r"\1\2 = [\6 for \3 in \4 if \5]",
            },
            # Pattern 4: Simple case with different indentation
            {
                "pattern": re.compile(
                    r"^(\s*)(\w+)\s*=\s*\[\]\s*$\n"
                    r"^(\s*)for\s+(\w+)\s+in\s+(.+?):\s*$\n"
                    r"^\3\s+\2\.append\(([^)]+)\)\s*$",
                    re.MULTILINE,
                ),
                "replacement": r"\1\2 = [\6 for \4 in \5]",
            },
        ]

        # Apply patterns
        modified = content
        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            replacement = pattern_info["replacement"]
            modified = pattern.sub(replacement, modified)

        # Additional pattern for extend
        extend_pattern = re.compile(
            r"(\s*)(\w+)\s*=\s*\[\]\s*\n"
            r"\1for\s+(\w+)\s+in\s+(.+?):\s*\n"
            r"\1\s+\2\.extend\(([^)]+)\)\s*(?:\n|$)",
            re.MULTILINE,
        )

        def replace_extend(match):
            indent, var_name, loop_var, iterable, extend_arg = match.groups()
            # For extend, we need to flatten
            return f"{indent}{var_name} = [item for {loop_var} in {iterable} for item in {extend_arg}]"

        modified = extend_pattern.sub(replace_extend, modified)

        if modified != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

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
        if fix_manual_comprehensions(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
