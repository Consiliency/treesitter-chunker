#!/usr/bin/env python3
"""Fix B904 errors by adding 'from e' to raise statements in except blocks."""

import re
import subprocess
from pathlib import Path


def fix_b904_in_file(file_path: Path) -> bool:
    """Fix B904 errors in a single file."""
    try:
        content = file_path.read_text()
        original = content

        # Pattern to find except blocks with raise statements
        pattern = re.compile(
            r"(\s*except\s+.*?\s+as\s+(\w+)\s*:\s*\n)"  # except ... as e:
            r"((?:.*\n)*?)"  # body before raise
            r"(\s*raise\s+)([^\n]+?)(\s*(?:#.*)?)\n",  # raise statement
            re.MULTILINE,
        )

        def replace_raise(match):
            except_line, var_name, body, raise_indent, raise_expr, comment = (
                match.groups()
            )

            # Skip if already has 'from'
            if " from " in raise_expr:
                return match.group(0)

            # Skip if it's just re-raising (bare raise or raise var_name)
            if raise_expr.strip() == "" or raise_expr.strip() == var_name:
                return match.group(0)

            # Add 'from var_name'
            return f"{except_line}{body}{raise_indent}{raise_expr} from {var_name}{comment}\n"

        content = pattern.sub(replace_raise, content)

        # Also handle except blocks without 'as e'
        pattern2 = re.compile(
            r"(\s*except\s+[^:\n]+:\s*\n)"  # except ...:
            r"((?:.*\n)*?)"  # body before raise
            r"(\s*raise\s+)([^\n]+?)(\s*(?:#.*)?)\n",  # raise statement
            re.MULTILINE,
        )

        def replace_raise2(match):
            except_line, body, raise_indent, raise_expr, comment = match.groups()

            # Skip if already has 'from' or if it's a bare raise
            if " from " in raise_expr or raise_expr.strip() == "":
                return match.group(0)

            # Add 'from None'
            return f"{except_line}{body}{raise_indent}{raise_expr} from None{comment}\n"

        content = pattern2.sub(replace_raise2, content)

        if content != original:
            file_path.write_text(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Find and fix B904 errors."""
    # Get all files with B904 errors
    result = subprocess.run(
        ["ruff", "check", "--select", "B904", ".", "--output-format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("No B904 errors found!")
        return

    import json

    try:
        errors = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Fallback to parsing text output
        print("Parsing ruff output as text...")
        files_to_fix = set()
        for line in result.stdout.splitlines():
            if "B904" in line and ":" in line:
                file_path = line.split(":")[0].strip()
                files_to_fix.add(file_path)

        fixed = 0
        for file_path in sorted(files_to_fix):
            path = Path(file_path)
            if path.exists() and fix_b904_in_file(path):
                print(f"Fixed: {file_path}")
                fixed += 1

        print(f"\nFixed {fixed} files")
        return

    files_to_fix = set()
    for error in errors:
        files_to_fix.add(error["filename"])

    fixed = 0
    for file_path in sorted(files_to_fix):
        path = Path(file_path)
        if fix_b904_in_file(path):
            print(f"Fixed: {file_path}")
            fixed += 1

    print(f"\nFixed {fixed} files")


if __name__ == "__main__":
    main()
