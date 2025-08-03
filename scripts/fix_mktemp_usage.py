#!/usr/bin/env python3
"""Fix S306 - Replace insecure mktemp with secure alternatives."""

import re
from pathlib import Path


def fix_mktemp_in_file(file_path: Path) -> list[str]:
    """Fix mktemp usage in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Pattern to find mktemp usage
    # Look for Path(tempfile.mktemp(suffix=".py"))
    pattern = r'Path\(tempfile\.mktemp\(suffix="([^"]+)"\)\)'

    def replace_mktemp(match):
        suffix = match.group(1)
        changes.append(f"Replaced mktemp with NamedTemporaryFile for suffix {suffix}")
        return f'Path(tempfile.NamedTemporaryFile(suffix="{suffix}", delete=False).name)'

    content = re.sub(pattern, replace_mktemp, content)

    # Alternative pattern for other mktemp usages
    pattern2 = r"tempfile\.mktemp\(([^)]*)\)"

    def replace_mktemp2(match):
        args = match.group(1)
        changes.append("Replaced mktemp with NamedTemporaryFile")
        if args:
            return f"tempfile.NamedTemporaryFile({args}, delete=False).name"
        return "tempfile.NamedTemporaryFile(delete=False).name"

    # Only apply second pattern if first didn't match
    if len(changes) == 0:
        content = re.sub(pattern2, replace_mktemp2, content)

    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    # Files with mktemp errors
    files_to_fix = [
        Path("/home/jenner/code/treesitter-chunker/tests/test_parallel.py"),
    ]

    total_changes = []

    for file_path in files_to_fix:
        if file_path.exists():
            print(f"\nChecking {file_path}...")
            changes = fix_mktemp_in_file(file_path)
            if changes:
                print(f"Fixed {len(changes)} mktemp usages in {file_path}")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal changes: {len(total_changes)}")


if __name__ == "__main__":
    main()
