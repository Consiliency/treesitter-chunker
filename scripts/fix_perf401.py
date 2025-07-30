#!/usr/bin/env python3
"""Fix PERF401 - Convert manual list comprehensions to proper list comprehensions."""

import re
from pathlib import Path


def fix_perf401_in_file(file_path: Path) -> bool:
    """Fix PERF401 issues in a file."""
    try:
        with Path(file_path).open("r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    original_content = content

    # Pattern 1: Simple append in for loop
    # result = []
    # for item in items:
    #     result.append(transform(item))
    pattern1 = re.compile(
        r"(\s*)(\w+)\s*=\s*\[\]\s*\n"  # list initialization
        r"(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n"  # for loop
        r"(\s*)\2\.append\(([^)]+)\)\s*(?:\n|$)",  # append call
        re.MULTILINE,
    )

    def replace_simple(match):
        indent1 = match.group(1)
        var_name = match.group(2)
        loop_var = match.group(4)
        iterable = match.group(5)
        expr = match.group(7).strip()

        # Replace variable references in expression
        expr = re.sub(r"\b" + re.escape(loop_var) + r"\b", loop_var, expr)

        return f"{indent1}{var_name} = [{expr} for {loop_var} in {iterable}]\n"

    content = pattern1.sub(replace_simple, content)

    # Pattern 2: Append with if condition
    # result = []
    # for item in items:
    #     if condition:
    #         result.append(transform(item))
    pattern2 = re.compile(
        r"(\s*)(\w+)\s*=\s*\[\]\s*\n"  # list initialization
        r"(\s*)for\s+(\w+)\s+in\s+([^:]+):\s*\n"  # for loop
        r"(\s*)if\s+([^:]+):\s*\n"  # if condition
        r"(\s*)\2\.append\(([^)]+)\)\s*(?:\n|$)",  # append call
        re.MULTILINE,
    )

    def replace_with_if(match):
        indent1 = match.group(1)
        var_name = match.group(2)
        loop_var = match.group(4)
        iterable = match.group(5)
        condition = match.group(7).strip()
        expr = match.group(9).strip()

        return f"{indent1}{var_name} = [{expr} for {loop_var} in {iterable} if {condition}]\n"

    content = pattern2.sub(replace_with_if, content)

    # Pattern 3: Multi-line append (more complex)
    # This is harder to handle with regex, so we'll use a simpler approach
    # Look for patterns like:
    # results = []
    # for ...:
    #     results.append(
    #         multi
    #         line
    #         expression
    #     )

    # For now, let's handle the most common cases
    if content != original_content:
        try:
            # Verify the syntax is still valid
            compile(content, file_path, "exec")

            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(content)
            return True
        except SyntaxError as e:
            print(f"Syntax error in {file_path} after fix: {e}")
            return False

    return False


def main():
    """Main function to fix PERF401 issues."""
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
        if fix_perf401_in_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
