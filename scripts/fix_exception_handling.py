#!/usr/bin/env python3
"""Fix BLE001 and B904 exception handling issues."""

import os
import re
from pathlib import Path


def fix_exception_handling(file_path: Path) -> bool:
    """Fix exception handling in a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Fix B904: Add 'from e' or 'from None' to raise statements in except blocks
        # Pattern to find except blocks with raise statements
        pattern = re.compile(
            r"(\s*)except\s+(\w+(?:\s*\.\s*\w+)*(?:\s*,\s*\w+(?:\s*\.\s*\w+)*)*)\s+as\s+(\w+)\s*:\s*\n"
            r"((?:.*\n)*?)(\s*)raise\s+([^;]+?)(?:\s*#.*)?$",
            re.MULTILINE,
        )

        def replace_raise(match):
            indent1, exceptions, var_name, body, indent2, raise_expr = match.groups()

            # Check if the raise already has 'from'
            if " from " in raise_expr:
                return match.group(0)

            # Check if it's re-raising the same exception
            if raise_expr.strip() == var_name:
                return match.group(0)

            # Add 'from e' to the raise statement
            return f"{indent1}except {exceptions} as {var_name}:\n{body}{indent2}raise {raise_expr} from {var_name}"

        content = pattern.sub(replace_raise, content)

        # Also handle except blocks without 'as e'
        pattern2 = re.compile(
            r"(\s*)except\s+(\w+(?:\s*\.\s*\w+)*(?:\s*,\s*\w+(?:\s*\.\s*\w+)*)*)\s*:\s*\n"
            r"((?:.*\n)*?)(\s*)raise\s+([^;]+?)(?:\s*#.*)?$",
            re.MULTILINE,
        )

        def replace_raise2(match):
            indent1, exceptions, body, indent2, raise_expr = match.groups()

            # Check if the raise already has 'from'
            if " from " in raise_expr:
                return match.group(0)

            # Add 'from None' to the raise statement
            return f"{indent1}except {exceptions}:\n{body}{indent2}raise {raise_expr} from None"

        content = pattern2.sub(replace_raise2, content)

        # Fix BLE001: Replace blind Exception catches with more specific ones
        # This is harder to do automatically, so we'll just add comments for manual review
        if "except Exception" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if re.match(r"\s*except\s+Exception\b", line) and (
                    i > 0
                    and "# TODO: Replace with specific exception"
                    not in lines[i - 1]
                ):
                    lines[i] = line + "  # TODO: Replace with specific exception"
            content = "\n".join(lines)

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False

    except Exception:
        print(f"Error processing {file_path}")
        return False


def main():
    """Fix exception handling in all Python files."""
    fixed_count = 0

    # Find all Python files
    for root, _, files in os.walk("."):
        # Skip virtual environments and build directories
        if any(
            skip in root
            for skip in [".venv", "venv", "__pycache__", "build", "dist", ".git"]
        ):
            continue

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                if fix_exception_handling(file_path):
                    print(f"Fixed: {file_path}")
                    fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
