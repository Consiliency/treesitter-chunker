#!/usr/bin/env python3
"""Fix G002 - Convert logging % formatting to lazy evaluation."""

import json
import re
import subprocess
from pathlib import Path


def fix_logging_in_file(file_path: Path) -> list[str]:
    """Fix logging % formatting in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Patterns for different logging methods
    logging_methods = [
        "logger.debug", "logger.info", "logger.warning", "logger.error",
        "logger.critical", "logger.exception",
        "logging.debug", "logging.info", "logging.warning", "logging.error",
        "logging.critical", "logging.exception",
        "log.debug", "log.info", "log.warning", "log.error",
        "log.critical", "log.exception",
    ]

    for method in logging_methods:
        # Pattern to match logging with % formatting
        # Matches: logger.info("msg %s" % value) or logger.info("msg %s" % (value,))
        pattern = rf'({re.escape(method)}\s*\(\s*)(["\'][^"\']*%[^"\']*["\'])\s*%\s*(\([^)]+\)|[^,)]+)(\s*\))'

        def replace_with_lazy(match):
            method_call = match.group(1)
            format_str = match.group(2)
            values = match.group(3)
            closing = match.group(4)

            # Remove parentheses if values is a tuple
            if values.startswith("(") and values.endswith(")"):
                values = values[1:-1]

            changes.append(f"Converted {method} to lazy evaluation")
            return f"{method_call}{format_str}, {values}{closing}"

        content = re.sub(pattern, replace_with_lazy, content, flags=re.MULTILINE | re.DOTALL)

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    print("Fixing G002 logging % format errors...")

    # Get all files with G002 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "G002", "--output-format", "json"],
        check=False, capture_output=True,
        text=True,
    )

    if not result.stdout:
        print("No G002 errors found")
        return

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse ruff output")
        return

    # Get unique files with errors
    files_with_errors = {Path(err["filename"]) for err in errors}
    print(f"Found {len(files_with_errors)} files with G002 errors")

    total_changes = []

    for file_path in sorted(files_with_errors):
        if file_path.exists():
            changes = fix_logging_in_file(file_path)
            if changes:
                print(f"\n{file_path}:")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal changes: {len(total_changes)}")

    # Check remaining errors
    result = subprocess.run(
        ["ruff", "check", "--select", "G002", "--statistics"],
        check=False, capture_output=True,
        text=True,
    )

    if result.stderr:
        print(f"\nRemaining G002 errors: {result.stderr.strip()}")


if __name__ == "__main__":
    main()
