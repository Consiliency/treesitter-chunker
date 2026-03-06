#!/usr/bin/env python3
"""Fix double Path() calls introduced by broken PTH123 fix."""

import re
from pathlib import Path


def fix_double_path(file_path: Path) -> bool:
    """Fix double Path() issues in a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    original_content = content

    # Fix patterns like Path(file_path).open("r", )
    content = re.sub(
        r"Path\(([^)]+)\)\.Path\(([^)]+)\)\.open\(",
        r"Path(\1).open(\2, ",
        content,
    )

    # Fix patterns like .open("w", )
    content = re.sub(r'\.Path\("([rwab]+)"\)\.open\(', r'.open("\1", ', content)

    # Fix patterns like .open('r', )
    content = re.sub(r"\.Path\('([rwab]+)'\)\.open\(", r".open('\1', ", content)

    if content != original_content:
        try:
            # Verify the syntax is still valid
            compile(content, file_path, "exec")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except SyntaxError as e:
            print(f"Syntax error in {file_path} after fix: {e}")
            return False

    return False


def main():
    """Main function to fix double Path() issues."""
    # Get all Python files
    python_files = []
    for pattern in ["**/*.py"]:
        python_files.extend(Path().glob(pattern))

    fixed_count = 0
    for file_path in python_files:
        if fix_double_path(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
