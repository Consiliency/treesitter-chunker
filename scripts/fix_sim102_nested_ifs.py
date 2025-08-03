#!/usr/bin/env python3
"""Fix SIM102 - Simplify nested if statements by combining with 'and'."""

import ast
import os
from pathlib import Path


class NestedIfSimplifier(ast.NodeTransformer):
    """AST transformer to simplify nested if statements."""

    def __init__(self):
        self.changes_made = []

    def visit_If(self, node):
        """Visit if statements to find nested ifs that can be combined."""
        # First, recursively visit children
        self.generic_visit(node)

        # Check if this if statement has only one statement in its body
        # and that statement is another if without an else
        if (len(node.body) == 1 and
            isinstance(node.body[0], ast.If) and
            not node.body[0].orelse and
            not node.orelse):

            inner_if = node.body[0]

            # Combine the conditions with 'and'
            combined_test = ast.BoolOp(
                op=ast.And(),
                values=[node.test, inner_if.test],
            )

            # Create new if statement with combined condition
            node.test = combined_test
            node.body = inner_if.body

            self.changes_made.append("Combined nested if statements")

        return node


def fix_file(file_path: Path) -> list[str]:
    """Fix nested if statements in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    simplifier = NestedIfSimplifier()
    new_tree = simplifier.visit(tree)

    if simplifier.changes_made:
        # Convert AST back to code
        try:
            import astor
            new_code = astor.to_source(new_tree)
        except ImportError:
            # Fallback to ast.unparse (Python 3.9+)
            new_code = ast.unparse(new_tree)

        file_path.write_text(new_code, encoding="utf-8")
        return simplifier.changes_made

    return []


def fix_file_with_text(file_path: Path) -> list[str]:
    """Alternative text-based approach for more complex cases."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    lines = content.splitlines()
    changes = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Look for if statements
        if stripped.startswith("if ") and stripped.endswith(":"):
            # Get indentation
            indent = len(line) - len(line.lstrip())

            # Check if next non-empty line is another if at deeper indentation
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                next_line = lines[j]
                next_stripped = next_line.strip()
                next_indent = len(next_line) - len(next_line.lstrip())

                # Check if it's a nested if
                if (next_stripped.startswith("if ") and
                    next_stripped.endswith(":") and
                    next_indent > indent):

                    # Look for the body of the inner if
                    k = j + 1
                    while k < len(lines) and not lines[k].strip():
                        k += 1

                    if k < len(lines):
                        # body_indent = len(lines[k]) - len(lines[k].lstrip())  # Not used currently

                        # Check if there's no else clause for both ifs
                        has_else = False
                        m = k
                        while m < len(lines):
                            line_indent = len(lines[m]) - len(lines[m].lstrip())
                            if line_indent <= indent:
                                break
                            if line_indent == next_indent and lines[m].strip().startswith("else"):
                                has_else = True
                                break
                            m += 1

                        if not has_else:
                            # Extract conditions
                            outer_cond = stripped[3:-1].strip()
                            inner_cond = next_stripped[3:-1].strip()

                            # Combine conditions
                            combined = f"if {outer_cond} and {inner_cond}:"

                            # Replace lines
                            lines[i] = " " * indent + combined

                            # Remove the inner if line
                            del lines[j]

                            # Adjust indentation of the body
                            while k < len(lines):
                                if lines[k].strip():
                                    current_indent = len(lines[k]) - len(lines[k].lstrip())
                                    if current_indent <= next_indent:
                                        break
                                    # Reduce indentation
                                    lines[k] = lines[k][4:]  # Remove 4 spaces
                                k += 1

                            changes.append(f"Combined nested if at line {i + 1}")
                            continue

        i += 1

    if changes:
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return changes


def main():
    """Main function."""
    # Find all Python files in the project
    project_root = Path(__file__).parent.parent

    # Directories to exclude
    exclude_dirs = {
        ".venv", "venv", "build", "dist", ".git", "ide",
        "node_modules", "grammars", "__pycache__", ".mypy_cache",
        ".ruff_cache", ".pytest_cache", "egg-info", "archive",
        "flask", "rust",
    }

    python_files = []
    for root, dirs, files in os.walk(project_root):
        # Remove excluded directories
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

    # First, run ruff to identify files with SIM102 errors
    import subprocess
    result = subprocess.run(
        ["ruff", "check", str(project_root), "--select", "SIM102", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
    )

    if result.stdout:
        import json
        try:
            errors = json.loads(result.stdout)
            files_with_errors = {Path(err["filename"]) for err in errors}

            for file_path in files_with_errors:
                if file_path in python_files:
                    # Try AST-based approach first
                    changes = fix_file(file_path)

                    # If no changes, try text-based approach
                    if not changes:
                        changes = fix_file_with_text(file_path)

                    if changes:
                        files_changed += 1
                        total_changes.extend(changes)
                        print(f"\n{file_path}:")
                        for change in changes:
                            print(f"  - {change}")
        except json.JSONDecodeError:
            print("Could not parse ruff output")

    print("\n\nSummary:")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {len(total_changes)}")


if __name__ == "__main__":
    main()
