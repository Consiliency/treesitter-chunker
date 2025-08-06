#!/usr/bin/env python3
"""Fix remaining F821 undefined name errors with pattern matching."""

import json
import re
import subprocess
from pathlib import Path


def fix_static_method_with_self():
    """Fix all @staticmethod methods that incorrectly use self."""
    fixes_made = 0

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

    # Group errors by file where self is undefined
    files_with_self_errors = {}
    for error in errors:
        if "'self'" in error["message"]:
            file_path = Path(error["filename"])
            if file_path not in files_with_self_errors:
                files_with_self_errors[file_path] = []
            files_with_self_errors[file_path].append(error["location"]["row"])

    for file_path, error_lines in files_with_self_errors.items():
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            modified = False

            # Find methods with self errors
            for line_num in error_lines:
                # Search backwards from error line to find method definition
                method_line = -1
                for i in range(line_num - 2, max(0, line_num - 50), -1):
                    if re.match(r"\s*def\s+\w+\s*\(", lines[i]):
                        method_line = i
                        break

                if method_line >= 0:
                    # Check if there's a @staticmethod decorator above
                    for i in range(method_line - 1, max(0, method_line - 10), -1):
                        if "@staticmethod" in lines[i]:
                            # Remove @staticmethod
                            indent = len(lines[i]) - len(lines[i].lstrip())
                            lines[i] = " " * indent + "# " + lines[i].strip()

                            # Add self to method signature if missing
                            method_def = lines[method_line]
                            if "def " in method_def and "(self" not in method_def:
                                # Handle various cases
                                if "()" in method_def:
                                    lines[method_line] = method_def.replace(
                                        "()",
                                        "(self)",
                                    )
                                else:
                                    # Insert self as first parameter
                                    match = re.match(
                                        r"(\s*def\s+\w+\s*\()(.*)(\)\s*.*:.*)",
                                        method_def,
                                    )
                                    if match:
                                        lines[method_line] = (
                                            match.group(1)
                                            + "self, "
                                            + match.group(2)
                                            + match.group(3)
                                        )
                                    else:
                                        # Fallback
                                        lines[method_line] = method_def.replace(
                                            "(",
                                            "(self, ",
                                            1,
                                        )

                            modified = True
                            fixes_made += 1
                            print(
                                f"Fixed @staticmethod in {file_path}:{method_line + 1}",
                            )
                            break

            if modified:
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes_made


def fix_undefined_variables():
    """Fix other undefined variables by analyzing context."""
    fixes_made = 0

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

    # Group by file
    files_to_fix = {}
    for error in errors:
        if "'self'" not in error["message"]:  # Skip self errors
            file_path = Path(error["filename"])
            if file_path not in files_to_fix:
                files_to_fix[file_path] = []

            # Extract undefined name
            match = re.search(r"Undefined name `(\w+)`", error["message"])
            if match:
                undefined_name = match.group(1)
                files_to_fix[file_path].append(
                    {
                        "line": error["location"]["row"],
                        "name": undefined_name,
                        "message": error["message"],
                    },
                )

    # Common fixes
    common_imports = {
        "List": "from typing import List",
        "Dict": "from typing import Dict",
        "Optional": "from typing import Optional",
        "Any": "from typing import Any",
        "Union": "from typing import Union",
        "Tuple": "from typing import Tuple",
        "Set": "from typing import Set",
        "Type": "from typing import Type",
        "Callable": "from typing import Callable",
        "Iterable": "from typing import Iterable",
        "Iterator": "from typing import Iterator",
        "Sequence": "from typing import Sequence",
        "Mapping": "from typing import Mapping",
        "cast": "from typing import cast",
        "TypeVar": "from typing import TypeVar",
        "Generic": "from typing import Generic",
        "Protocol": "from typing import Protocol",
        "TypedDict": "from typing import TypedDict",
        "Literal": "from typing import Literal",
        "Final": "from typing import Final",
        "ClassVar": "from typing import ClassVar",
        "overload": "from typing import overload",
        "NoReturn": "from typing import NoReturn",
        "AsyncIterator": "from typing import AsyncIterator",
        "AsyncIterable": "from typing import AsyncIterable",
        "AsyncGenerator": "from typing import AsyncGenerator",
        "ContextManager": "from typing import ContextManager",
        "AsyncContextManager": "from typing import AsyncContextManager",
        "Counter": "from collections import Counter",
        "defaultdict": "from collections import defaultdict",
        "deque": "from collections import deque",
        "OrderedDict": "from collections import OrderedDict",
        "ChainMap": "from collections import ChainMap",
        "namedtuple": "from collections import namedtuple",
        "Path": "from pathlib import Path",
        "PurePath": "from pathlib import PurePath",
        "datetime": "from datetime import datetime",
        "timedelta": "from datetime import timedelta",
        "date": "from datetime import date",
        "time": "from datetime import time",
        "timezone": "from datetime import timezone",
        "ABC": "from abc import ABC",
        "abstractmethod": "from abc import abstractmethod",
        "dataclass": "from dataclasses import dataclass",
        "field": "from dataclasses import field",
        "fields": "from dataclasses import fields",
        "asdict": "from dataclasses import asdict",
        "astuple": "from dataclasses import astuple",
        "replace": "from dataclasses import replace",
        "InitVar": "from dataclasses import InitVar",
        "MISSING": "from dataclasses import MISSING",
        "KW_ONLY": "from dataclasses import KW_ONLY",
        "Enum": "from enum import Enum",
        "IntEnum": "from enum import IntEnum",
        "Flag": "from enum import Flag",
        "IntFlag": "from enum import IntFlag",
        "auto": "from enum import auto",
        "unique": "from enum import unique",
    }

    for file_path, undefined_vars in files_to_fix.items():
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Collect imports to add
            imports_to_add = set()
            for var_info in undefined_vars:
                var_name = var_info["name"]
                if var_name in common_imports:
                    import_line = common_imports[var_name]
                    # Check if import already exists
                    if not any(import_line in line for line in lines):
                        imports_to_add.add(import_line)

            if imports_to_add:
                # Find where to insert imports
                insert_pos = 0
                has_future_import = False

                for i, line in enumerate(lines):
                    if line.startswith("from __future__ import"):
                        has_future_import = True
                        insert_pos = i + 1
                    elif line.startswith(("import ", "from ")):
                        if not has_future_import:
                            insert_pos = i + 1
                    elif (
                        line.strip()
                        and not line.strip().startswith("#")
                        and not line.strip().startswith('"""')
                    ):
                        if insert_pos == 0:
                            insert_pos = i
                        break

                # Add imports
                for imp in sorted(imports_to_add):
                    lines.insert(insert_pos, imp)
                    insert_pos += 1
                    fixes_made += 1
                    print(f"Added import to {file_path}: {imp}")

                # Add blank line if needed
                if insert_pos < len(lines) and lines[insert_pos].strip():
                    lines.insert(insert_pos, "")

                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        except Exception as e:
            print(f"Error fixing imports in {file_path}: {e}")

    return fixes_made


def main():
    """Main function."""
    print("Fixing remaining F821 undefined name errors...")

    total_fixes = 0

    # Fix @staticmethod issues
    print("\n1. Fixing @staticmethod methods using self...")
    fixes = fix_static_method_with_self()
    total_fixes += fixes
    print(f"Fixed {fixes} @staticmethod issues")

    # Fix missing imports
    print("\n2. Fixing missing imports...")
    fixes = fix_undefined_variables()
    total_fixes += fixes
    print(f"Fixed {fixes} import issues")

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
        print("\nAll F821 errors fixed!")

    print(f"\nTotal fixes applied: {total_fixes}")


if __name__ == "__main__":
    main()
