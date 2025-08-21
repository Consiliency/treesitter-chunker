#!/usr/bin/env python3
"""Fix remaining F821 undefined name errors."""

import json
import re
import subprocess
from pathlib import Path


def fix_class_name_references():
    """Fix class name references in nested functions."""
    fixes_made = []

    # Specific files with class name reference issues
    files_to_fix = {
        "/home/jenner/code/treesitter-chunker/chunker/context/languages/javascript.py": {
            "JavaScriptContextProvider": "self.__class__",
        },
        "/home/jenner/code/treesitter-chunker/chunker/context/languages/python.py": {
            "PythonContextProvider": "self.__class__",
        },
    }

    for file_path, replacements in files_to_fix.items():
        try:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text(encoding="utf-8")
            original = content

            for old_name, new_name in replacements.items():
                # Replace class name references in nested functions
                pattern = rf"\b{old_name}\b(?=\._)"
                content = re.sub(pattern, new_name, content)

            if content != original:
                path.write_text(content, encoding="utf-8")
                fixes_made.append(f"Fixed class name references in {file_path}")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes_made


def fix_staticmethod_self_references():
    """Fix @staticmethod methods that incorrectly use self."""
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
        if "'self'" in error["message"] and "Undefined name" in error["message"]:
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

            # Find methods with self errors
            for error in errors:
                line_num = error["line"] - 1  # 0-based

                # Search backwards for the method definition
                method_line = -1
                for i in range(line_num, -1, -1):
                    if lines[i].strip().startswith("def "):
                        method_line = i
                        break

                if method_line >= 0:
                    # Check if it's a @staticmethod
                    is_static = False
                    for i in range(method_line - 1, -1, -1):
                        if lines[i].strip() == "":
                            continue
                        if "@staticmethod" in lines[i]:
                            is_static = True
                            break
                        if not lines[i].strip().startswith("@"):
                            break

                    if is_static:
                        # Remove @staticmethod decorator
                        for i in range(method_line - 1, -1, -1):
                            if "@staticmethod" in lines[i]:
                                indent = len(lines[i]) - len(lines[i].lstrip())
                                lines[i] = " " * indent + "# " + lines[i].strip()
                                modified = True

                                # Add self parameter if missing
                                method_def = lines[method_line]
                                if "def " in method_def and "(self" not in method_def:
                                    paren_idx = method_def.find("(")
                                    if paren_idx != -1:
                                        close_paren = method_def.find(")", paren_idx)
                                        params = method_def[
                                            paren_idx + 1 : close_paren
                                        ].strip()
                                        if params:
                                            lines[method_line] = (
                                                method_def[: paren_idx + 1]
                                                + "self, "
                                                + method_def[paren_idx + 1 :]
                                            )
                                        else:
                                            lines[method_line] = (
                                                method_def[: paren_idx + 1]
                                                + "self"
                                                + method_def[paren_idx + 1 :]
                                            )

                                fixes_made.append(
                                    f"Fixed @staticmethod in {file_path}:{method_line + 1}",
                                )
                                break

            if modified:
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes_made


def fix_missing_type_annotations():
    """Fix missing type annotations that cause F821 errors."""
    fixes_made = []

    # Common missing types
    type_fixes = {
        "chunker/languages/wasm.py": [
            ("List[", "list["),
            ("Dict[", "dict["),
            ("Optional[", ""),  # Remove Optional, use | None
            ("Union[", ""),  # Remove Union, use |
        ],
        "chunker/languages/zig.py": [
            ("List[", "list["),
            ("Dict[", "dict["),
        ],
    }

    for file_path, replacements in type_fixes.items():
        try:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text(encoding="utf-8")
            original = content

            # Remove old typing imports if switching to built-in types
            content = re.sub(r"from typing import .*List.*\n", "", content)
            content = re.sub(r"from typing import .*Dict.*\n", "", content)

            for old, new in replacements:
                content = content.replace(old, new)

            if content != original:
                path.write_text(content, encoding="utf-8")
                fixes_made.append(f"Fixed type annotations in {file_path}")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes_made


def main():
    """Main function."""
    print("Fixing remaining F821 undefined name errors...")

    all_fixes = []

    # Fix class name references
    print("\n1. Fixing class name references in nested functions...")
    fixes = fix_class_name_references()
    all_fixes.extend(fixes)
    for fix in fixes:
        print(f"  - {fix}")

    # Fix @staticmethod issues
    print("\n2. Fixing @staticmethod methods using self...")
    fixes = fix_staticmethod_self_references()
    all_fixes.extend(fixes)
    for fix in fixes:
        print(f"  - {fix}")

    # Fix missing type annotations
    print("\n3. Fixing missing type annotations...")
    fixes = fix_missing_type_annotations()
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
    else:
        print("\nNo statistics available")

    print(f"\nTotal fixes applied: {len(all_fixes)}")


if __name__ == "__main__":
    main()
