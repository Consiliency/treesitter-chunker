#!/usr/bin/env python3
"""Script to fix E722 (bare except) errors."""

import re
from pathlib import Path


def fix_bare_except(file_path):
    """Fix E722 errors in a single file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content

        # Replace bare except: with except Exception:
        # Pattern matches "except:" with optional spaces, on its own line
        pattern = re.compile(r"^(\s*)except\s*:\s*$", re.MULTILINE)

        content = pattern.sub(r"\1except Exception:", content)

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

\1except (AttributeError, IOError, IndexError) as \2:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix E722 errors in the codebase."""
    # Get all Python files
    files_to_check = []
    for pattern in ["chunker/**/*.py", "tests/**/*.py", "cli/**/*.py", "benchmarks/**/*.py", "examples/**/*.py", "scripts/**/*.py"]:
        files_to_check.extend(Path().glob(pattern))

    fixed = 0
    total = 0

    for file_path in files_to_check:
        if "fix_bare_except.py" in str(file_path):
            continue

        # Check if file has bare except
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                if re.search(r"^\s*except\s*:\s*$", content, re.MULTILINE):
                    total += 1
                    if fix_bare_except(file_path):
                        print(f"Fixed: {file_path}")
                        fixed += 1
\1except (AttributeError, IndexError, KeyError) as \2:
            print(f"Error checking {file_path}: {e}")

    print(f"\nFixed {fixed}/{total} files with bare except clauses")


if __name__ == "__main__":
    main()
