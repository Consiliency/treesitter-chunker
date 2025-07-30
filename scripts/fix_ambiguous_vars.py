#!/usr/bin/env python3
"""Script to fix E741 (ambiguous variable name) errors."""

import re
from pathlib import Path


def fix_ambiguous_vars(file_path):
    """Fix E741 errors in a single file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content

        # Replace common patterns of ambiguous variable names
        # Pattern 1: for l in ... (replace l with line)
        content = re.sub(r"\bfor\s+l\s+in\b", "for line in", content)

        # Pattern 2: len(l) (replace l with line)
        content = re.sub(r"\blen\(l\)", "len(line)", content)

        # Pattern 3: (l) in comprehensions
        content = re.sub(r"\(l\)\s+for\s+l\s+in", "(line) for line in", content)

        # Pattern 4: Just 'l' in comprehensions after 'for'
        content = re.sub(r"\s+l\s+for\s+l\s+in", " line for line in", content)

        # Pattern 5: Standalone 'l' variable references (more conservative)
        # Only in list comprehensions and similar contexts
        content = re.sub(r"(?<=\[)l(?=\s+for)", "line", content)
        content = re.sub(r"(?<=\()l(?=\s+for)", "line", content)
        content = re.sub(r"(?<=\s)l(?=\[)", "line", content)
        content = re.sub(r"(?<=\s)l(?=\.)", "line", content)

        # Pattern for 'O' (replace with obj)
        content = re.sub(r"\bfor\s+O\s+in\b", "for obj in", content)
        content = re.sub(r"\(O\)\s+for\s+O\s+in", "(obj) for obj in", content)

        # Pattern for 'I' (replace with idx)
        content = re.sub(r"\bfor\s+I\s+in\b", "for idx in", content)
        content = re.sub(r"\(I\)\s+for\s+I\s+in", "(idx) for idx in", content)

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except (OSError, FileNotFoundError, IndexError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix E741 errors in the codebase."""
    # Specific files with E741 errors
    files_to_fix = [
        "chunker/fallback/strategies/line_based.py",
        "chunker/fallback/strategies/markdown.py",
        "chunker/processors/config.py",
        "chunker/strategies/composite.py",
        "examples/multi_language_demo.py",
        "tests/test_cli_integration_advanced.py",
    ]

    fixed = 0
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            if fix_ambiguous_vars(path):
                print(f"Fixed: {file_path}")
                fixed += 1
        else:
            print(f"Not found: {file_path}")

    print(f"\nFixed {fixed} files with ambiguous variable names")


if __name__ == "__main__":
    main()
