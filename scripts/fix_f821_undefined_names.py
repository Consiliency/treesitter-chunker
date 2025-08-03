#!/usr/bin/env python3
"""Fix F821 - Undefined name errors."""

import ast
import json
import subprocess
from pathlib import Path


class UndefinedNameFixer(ast.NodeTransformer):
    """AST transformer to fix undefined name errors."""

    def __init__(self, undefined_names: set[str]):
        self.undefined_names = undefined_names
        self.changes_made = []
        self.in_static_method = False
        self.current_class = None
        self.class_methods = {}

    def visit_ClassDef(self, node):
        """Track class context."""
        old_class = self.current_class
        self.current_class = node.name

        # Collect method names and their decorators
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                decorators = [d.id if isinstance(d, ast.Name) else
                             d.attr if isinstance(d, ast.Attribute) else None
                             for d in item.decorator_list]
                self.class_methods[item.name] = {
                    "is_static": "staticmethod" in decorators,
                    "is_class": "classmethod" in decorators,
                }

        self.generic_visit(node)
        self.current_class = old_class
        return node

    def visit_FunctionDef(self, node):
        """Check if function is static method and fix accordingly."""
        # Check if this is a static method using self
        is_static = any(isinstance(d, ast.Name) and d.id == "staticmethod"
                       for d in node.decorator_list)

        old_static = self.in_static_method
        self.in_static_method = is_static

        if is_static and self._function_uses_self(node):
            # Remove @staticmethod decorator
            node.decorator_list = [d for d in node.decorator_list
                                 if not (isinstance(d, ast.Name) and d.id == "staticmethod")]

            # Add self parameter if not present
            if not node.args.args or node.args.args[0].arg != "self":
                self_arg = ast.arg(arg="self", annotation=None)
                node.args.args.insert(0, self_arg)
                self.changes_made.append(f"Converted {node.name} from @staticmethod to instance method")

        self.generic_visit(node)
        self.in_static_method = old_static
        return node

    def _function_uses_self(self, node):
        """Check if function body uses 'self'."""
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == "self":
                return True
        return False

    def visit_Name(self, node):
        """Fix undefined names."""
        if node.id in self.undefined_names:
            # Handle specific cases
            if node.id == "List" and isinstance(node.ctx, ast.Load):
                # This is likely a type annotation - needs import
                self.changes_made.append("Need to import List from typing")
            elif node.id == "Optional" and isinstance(node.ctx, ast.Load):
                self.changes_made.append("Need to import Optional from typing")
        return node


def get_undefined_names_from_file(file_path: Path) -> list[tuple[int, str]]:
    """Get undefined names in a file using ruff."""
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json", str(file_path)],
        check=False, capture_output=True,
        text=True,
    )

    if result.stdout:
        try:
            errors = json.loads(result.stdout)
            return [(err["location"]["row"], err["message"].split("'")[1])
                    for err in errors if err["code"] == "F821"]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
    return []


def fix_file(file_path: Path) -> list[str]:
    """Fix undefined names in a single file."""
    undefined_names = get_undefined_names_from_file(file_path)
    if not undefined_names:
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    # Extract unique undefined names
    unique_names = set(name for _, name in undefined_names)

    fixer = UndefinedNameFixer(unique_names)
    new_tree = fixer.visit(tree)

    # Add necessary imports
    imports_to_add = []
    for change in fixer.changes_made:
        if "import List" in change:
            imports_to_add.append("from typing import List")
        elif "import Optional" in change:
            imports_to_add.append("from typing import Optional")

    if fixer.changes_made or imports_to_add:
        # Convert AST back to code
        try:
            import astor
            new_code = astor.to_source(new_tree)
        except ImportError:
            new_code = ast.unparse(new_tree)

        # Add imports at the top
        if imports_to_add:
            lines = new_code.splitlines()
            # Find where to insert imports
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith("#") and not line.startswith('"""'):
                    insert_pos = i
                    break

            for imp in imports_to_add:
                lines.insert(insert_pos, imp)
                insert_pos += 1

            new_code = "\n".join(lines)

        file_path.write_text(new_code, encoding="utf-8")
        return fixer.changes_made

    return []


def fix_simple_static_method_issues():
    """Fix simple cases where @staticmethod uses self."""
    project_root = Path(__file__).parent.parent

    # Get all files with F821 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
        cwd=project_root,
    )

    if not result.stdout:
        return

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        return

    files_to_fix = {}
    for error in errors:
        if error["code"] == "F821" and "'self'" in error["message"]:
            file_path = Path(error["filename"])
            if file_path not in files_to_fix:
                files_to_fix[file_path] = []
            files_to_fix[file_path].append(error["location"]["row"])

    for file_path, line_numbers in files_to_fix.items():
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Simple text-based fix for @staticmethod using self
            for i in range(len(lines)):
                if "@staticmethod" in lines[i]:
                    # Check if the next function uses self
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if "def " in lines[j]:
                            # Check if this function is one that uses self
                            func_line = j + 1
                            if func_line in line_numbers:
                                # Remove @staticmethod
                                lines[i] = "    # " + lines[i].strip()
                                # Add self parameter if missing
                                if "self" not in lines[j]:
                                    lines[j] = lines[j].replace("(", "(self, ", 1)
                                    if "()" in lines[j]:
                                        lines[j] = lines[j].replace("()", "(self)")
                                print(f"Fixed @staticmethod using self in {file_path}:{func_line}")
                            break

            file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")


def main():
    """Main function."""
    print("Fixing F821 undefined name errors...")

    # First, fix simple @staticmethod issues
    fix_simple_static_method_issues()

    # Then handle other undefined names
    project_root = Path(__file__).parent.parent

    # Get remaining F821 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
        cwd=project_root,
    )

    if result.stdout:
        try:
            errors = json.loads(result.stdout)
            remaining_files = set(Path(err["filename"]) for err in errors)

            for file_path in remaining_files:
                if file_path.exists():
                    changes = fix_file(file_path)
                    if changes:
                        print(f"\n{file_path}:")
                        for change in changes:
                            print(f"  - {change}")
        except json.JSONDecodeError:
            print("Could not parse ruff output")

    # Check remaining errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--statistics"],
        check=False, capture_output=True,
        text=True,
        cwd=project_root,
    )

    if result.stderr:
        print(f"\nRemaining F821 errors: {result.stderr.strip()}")
    else:
        print("\nAll F821 errors fixed!")


if __name__ == "__main__":
    main()
