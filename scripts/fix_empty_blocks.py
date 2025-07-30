#!/usr/bin/env python3
"""Fix empty blocks that cause syntax errors."""

import re
from pathlib import Path


def fix_empty_blocks(file_path: Path) -> bool:
    """Fix empty if TYPE_CHECKING and try blocks."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content

        # Fix empty TYPE_CHECKING blocks
        # Pattern: if TYPE_CHECKING: followed by empty lines and then a non-indented line
        pattern1 = re.compile(
            r"(if\s+TYPE_CHECKING\s*:)\s*\n(\s*\n)+(?=\S)",
            re.MULTILINE,
        )
        content = pattern1.sub(r"\1\n    pass\n\n", content)

        # Fix empty try blocks
        # Pattern: try: followed by empty lines and then except
        pattern2 = re.compile(
            r"(\s*try\s*:)\s*\n(\s*\n)*(\s*except)",
            re.MULTILINE,
        )
        content = pattern2.sub(r"\1\n    pass\n\3", content)

        # Fix empty except blocks
        pattern3 = re.compile(
            r"(\s*except[^:]*:)\s*\n(\s*\n)+(\s*(?:except|finally|else|\S))",
            re.MULTILINE,
        )
        content = pattern3.sub(r"\1\n    pass\n\3", content)

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

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
        "TypeScript",
    }

    python_files = [
        f for f in python_files if not any(exc in f.parts for exc in exclude_dirs)
    ]

    fixed_count = 0
    for file_path in python_files:
        if fix_empty_blocks(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
