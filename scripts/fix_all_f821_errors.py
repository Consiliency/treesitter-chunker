#!/usr/bin/env python3
"""Fix all F821 undefined name errors comprehensively."""

import json
import subprocess
from pathlib import Path


def fix_static_method_self_errors():
    """Fix @staticmethod methods that use self."""
    fixes_made = []

    # Get all F821 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout:
        return fixes_made

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        return fixes_made

    # Group errors by file
    files_to_fix = {}
    for error in errors:
        if "'self'" in error["message"]:
            file_path = Path(error["filename"])
            if file_path not in files_to_fix:
                files_to_fix[file_path] = []
            files_to_fix[file_path].append(
                {
                    "line": error["location"]["row"],
                    "message": error["message"],
                },
            )

    for file_path, errors in files_to_fix.items():
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            modified = False

            # Find @staticmethod decorators and their functions
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if line == "@staticmethod" or line.startswith("@staticmethod"):
                    # Find the function definition
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith("def "):
                        j += 1

                    if j < len(lines):
                        func_line_num = j + 1  # 1-based line number

                        # Check if this function has self errors
                        has_self_error = any(
                            err["line"] >= func_line_num for err in errors
                        )

                        if has_self_error:
                            # Remove @staticmethod
                            indent = len(lines[i]) - len(lines[i].lstrip())
                            lines[i] = " " * indent + "# " + lines[i].strip()

                            # Add self parameter if missing
                            func_line = lines[j]
                            if "def " in func_line and "(self" not in func_line:
                                # Find the opening parenthesis
                                paren_idx = func_line.find("(")
                                if paren_idx != -1:
                                    if func_line[paren_idx + 1] == ")":
                                        # Empty parameter list
                                        lines[j] = (
                                            func_line[: paren_idx + 1]
                                            + "self"
                                            + func_line[paren_idx + 1 :]
                                        )
                                    else:
                                        # Has parameters
                                        lines[j] = (
                                            func_line[: paren_idx + 1]
                                            + "self, "
                                            + func_line[paren_idx + 1 :]
                                        )

                            modified = True
                            fixes_made.append(
                                f"Fixed @staticmethod in {file_path}:{func_line_num}",
                            )

                i += 1

            if modified:
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes_made


def fix_missing_imports():
    """Fix missing imports for common undefined names."""
    fixes_made = []

    # Common missing imports
    import_map = {
        "List": "from typing import List",
        "Dict": "from typing import Dict",
        "Optional": "from typing import Optional",
        "Any": "from typing import Any",
        "Union": "from typing import Union",
        "Tuple": "from typing import Tuple",
        "Set": "from typing import Set",
        "Type": "from typing import Type",
        "Callable": "from typing import Callable",
        "Iterator": "from typing import Iterator",
        "Iterable": "from typing import Iterable",
        "TypeVar": "from typing import TypeVar",
        "cast": "from typing import cast",
        "overload": "from typing import overload",
        "Protocol": "from typing import Protocol",
        "TypedDict": "from typing import TypedDict",
        "Literal": "from typing import Literal",
        "Final": "from typing import Final",
        "ClassVar": "from typing import ClassVar",
    }

    # Get remaining F821 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout:
        return fixes_made

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        return fixes_made

    # Group by file and undefined name
    files_to_fix = {}
    for error in errors:
        # Extract undefined name from message
        if "Undefined name" in error["message"]:
            parts = error["message"].split("'")
            if len(parts) >= 3:
                undefined_name = parts[1]
                if undefined_name in import_map:
                    file_path = Path(error["filename"])
                    if file_path not in files_to_fix:
                        files_to_fix[file_path] = set()
                    files_to_fix[file_path].add(undefined_name)

    for file_path, undefined_names in files_to_fix.items():
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Find where to insert imports
            insert_pos = 0
            has_future_import = False

            for i, line in enumerate(lines):
                if line.startswith("from __future__ import"):
                    has_future_import = True
                    insert_pos = i + 1
                elif line.startswith(("import ", "from ")):
                    # Track last import line for potential use
                    if not has_future_import:
                        insert_pos = i + 1
                elif (
                    line.strip()
                    and not line.startswith("#")
                    and not line.startswith('"""')
                ):
                    if insert_pos == 0:
                        insert_pos = i
                    break

            # Add imports
            imports_to_add = []
            for name in undefined_names:
                if name in import_map:
                    import_line = import_map[name]
                    # Check if import already exists
                    if not any(import_line in line for line in lines):
                        imports_to_add.append(import_line)

            if imports_to_add:
                # Insert imports
                for imp in sorted(imports_to_add):
                    lines.insert(insert_pos, imp)
                    insert_pos += 1

                # Add blank line if needed
                if insert_pos < len(lines) and lines[insert_pos].strip():
                    lines.insert(insert_pos, "")

                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                fixes_made.extend(
                    [f"Added '{imp}' to {file_path}" for imp in imports_to_add],
                )

        except Exception as e:
            print(f"Error fixing imports in {file_path}: {e}")

    return fixes_made


def main():
    """Main function."""
    print("Fixing all F821 undefined name errors...")

    all_fixes = []

    # First, fix @staticmethod issues
    print("\n1. Fixing @staticmethod methods using self...")
    fixes = fix_static_method_self_errors()
    all_fixes.extend(fixes)
    for fix in fixes:
        print(f"  - {fix}")

    # Then fix missing imports
    print("\n2. Fixing missing imports...")
    fixes = fix_missing_imports()
    all_fixes.extend(fixes)
    for fix in fixes:
        print(f"  - {fix}")

    # Check remaining errors
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--statistics"],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.stderr:
        remaining = result.stderr.strip()
        print(f"\nRemaining F821 errors: {remaining}")

        # Show a few examples
        result = subprocess.run(
            ["ruff", "check", "--select", "F821"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            lines = result.stdout.strip().split("\n")[:10]
            print("\nExamples of remaining errors:")
            for line in lines:
                print(f"  {line}")
    else:
        print("\nAll F821 errors fixed!")

    print(f"\nTotal fixes applied: {len(all_fixes)}")


if __name__ == "__main__":
    main()
