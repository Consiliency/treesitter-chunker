#!/usr/bin/env python3
"""Fix RUF039 - Convert regex patterns to raw strings (including multiline)."""

import json
import re
import subprocess
from pathlib import Path


def fix_regex_in_file(file_path: Path) -> list[str]:
    """Fix regex patterns in a file using AST-aware approach."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Get specific line numbers with RUF039 errors from ruff
    result = subprocess.run(
        ["ruff", "check", str(file_path), "--select", "RUF039", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
    )

    if not result.stdout:
        return []

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    # Sort errors by line number in reverse to fix from bottom to top
    errors.sort(key=lambda e: e["location"]["row"], reverse=True)

    lines = content.splitlines()

    for error in errors:
        line_num = error["location"]["row"] - 1  # 0-based

        # Find the string literal that needs to be raw
        # Look for patterns like 'pattern' or "pattern"
        line = lines[line_num] if line_num < len(lines) else ""

        # Check if it's already a raw string
        if re.search(r'\br["\']', line):
            continue

        # Find quoted strings in the line
        # Handle both single and double quotes
        def make_raw(match):
            quote = match.group(1)
            content = match.group(2)
            # Only convert if it has backslashes
            if "\\" in content:
                changes.append(f"Line {line_num + 1}: Converted string to raw")
                return f"r{quote}{content}{quote}"
            return match.group(0)

        # Pattern to match quoted strings (not already raw)
        line = re.sub(r'(?<![rb])(["\'])([^"\']*\\[^"\']*)\1', make_raw, line)
        lines[line_num] = line

    if changes:
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return changes


def main():
    """Main function."""
    print("Fixing RUF039 unraw regex patterns...")

    # First get all files with RUF039 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "RUF039", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
    )

    if not result.stdout:
        print("No RUF039 errors found")
        return

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse ruff output")
        return

    # Get unique files with errors
    files_with_errors = {Path(err["filename"]) for err in errors}
    print(f"Found {len(files_with_errors)} files with RUF039 errors")

    total_changes = []

    for file_path in sorted(files_with_errors):
        if file_path.exists():
            changes = fix_regex_in_file(file_path)
            if changes:
                print(f"\n{file_path}:")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal changes: {len(total_changes)}")

    # Check remaining errors
    result = subprocess.run(
        ["ruff", "check", "--select", "RUF039", "--statistics"],
        check=False, capture_output=True,
        text=True,
    )

    if result.stderr:
        print(f"\nRemaining RUF039 errors: {result.stderr.strip()}")


if __name__ == "__main__":
    main()
