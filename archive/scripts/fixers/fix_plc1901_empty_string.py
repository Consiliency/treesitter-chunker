#!/usr/bin/env python3
"""Fix PLC1901 - Replace empty string comparisons."""

import json
import re
import subprocess
from pathlib import Path


def fix_empty_string_in_file(file_path: Path) -> list[str]:
    """Fix empty string comparisons in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Patterns to fix
    replacements = [
        # x == "" -> not x  (but be careful with edge cases)
        (
            r'(\s+)if\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*==\s*["\'][\'"]\s*:',
            r"\1if not \2:",
        ),
        # x != "" -> x
        (
            r'(\s+)if\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*!=\s*["\'][\'"]\s*:',
            r"\1if \2:",
        ),
        # return x == "" -> return not x
        (
            r'(\s+)return\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*==\s*["\'][\'"]',
            r"\1return not \2",
        ),
        # return x != "" -> return bool(x)
        (
            r'(\s+)return\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*!=\s*["\'][\'"]',
            r"\1return bool(\2)",
        ),
        # Simple comparisons in conditionals
        (r'\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*==\s*["\'][\'"]\s+', r" not \1 "),
        (r'\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\s*!=\s*["\'][\'"]\s+', r" \1 "),
    ]

    for pattern, replacement in replacements:
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            changes.append(f"Fixed {len(matches)} empty string comparisons")

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    print("Fixing PLC1901 empty string comparison errors...")

    # Get all files with PLC1901 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "PLC1901", "--output-format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout:
        print("No PLC1901 errors found")
        return

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse ruff output")
        return

    # Get unique files with errors
    files_with_errors = {Path(err["filename"]) for err in errors}
    print(f"Found {len(files_with_errors)} files with PLC1901 errors")

    total_changes = []

    for file_path in sorted(files_with_errors):
        if file_path.exists():
            changes = fix_empty_string_in_file(file_path)
            if changes:
                print(f"\n{file_path}:")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal changes: {len(total_changes)}")

    # Check remaining errors
    result = subprocess.run(
        ["ruff", "check", "--select", "PLC1901", "--statistics"],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.stderr:
        print(f"\nRemaining PLC1901 errors: {result.stderr.strip()}")


if __name__ == "__main__":
    main()
