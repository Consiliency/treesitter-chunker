#!/usr/bin/env python3
"""Fix RUF039 - Convert regex patterns to raw strings."""

import re
from pathlib import Path


def fix_regex_patterns_in_file(file_path: Path) -> list[str]:
    """Fix regex patterns in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Patterns to find regex functions with string literals
    regex_functions = [
        "re.compile",
        "re.search",
        "re.match",
        "re.findall",
        "re.finditer",
        "re.sub",
        "re.subn",
        "re.split",
    ]

    # For each regex function, find calls with non-raw strings
    for func in regex_functions:
        # Pattern to match function calls with quoted strings (not raw strings)
        # Matches: func("pattern") or func('pattern')
        pattern = rf'({re.escape(func)}\s*\(\s*)(["\'])([^"\']*?)(\2)'

        def replace_with_raw(match):
            func_call = match.group(1)
            quote = match.group(2)
            pattern_str = match.group(3)

            # Check if pattern contains backslashes that need raw string
            if "\\" in pattern_str:
                changes.append(f"Converted {func} pattern to raw string")
                return f"{func_call}r{quote}{pattern_str}{quote}"
            return match.group(0)

        content = re.sub(pattern, replace_with_raw, content)

    # Also handle patterns passed as variables to regex functions
    # Pattern: pattern = "regex\\pattern" followed by re.func(pattern)
    pattern_var = r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(["\'])([^"\']*\\[^"\']*)\3'

    def check_pattern_var(match):
        indent = match.group(1)
        var_name = match.group(2)
        quote = match.group(3)
        pattern_str = match.group(4)

        # Check if this variable is used in a regex function nearby
        if any(
            f"{func}({var_name}" in content or f"{func}( {var_name}" in content
            for func in regex_functions
        ):
            changes.append(f"Converted pattern variable '{var_name}' to raw string")
            return f"{indent}{var_name} = r{quote}{pattern_str}{quote}"
        return match.group(0)

    content = re.sub(pattern_var, check_pattern_var, content)

    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    # Find all Python files in the project
    project_root = Path(__file__).parent.parent

    # Directories to exclude
    exclude_dirs = {
        ".venv",
        "venv",
        "build",
        "dist",
        ".git",
        "ide",
        "node_modules",
        "grammars",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "egg-info",
        "archive",
    }

    python_files = [
        py_file
        for py_file in project_root.rglob("*.py")
        if not any(exc in str(py_file) for exc in exclude_dirs)
    ]

    print(f"Found {len(python_files)} Python files to check")

    total_changes = []
    files_changed = 0

    # First, run ruff to identify files with RUF039 errors
    import subprocess

    result = subprocess.run(
        [
            "ruff",
            "check",
            str(project_root),
            "--select",
            "RUF039",
            "--output-format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        import json

        try:
            errors = json.loads(result.stdout)
            files_with_errors = {Path(err["filename"]) for err in errors}

            for file_path in files_with_errors:
                if file_path.exists():
                    changes = fix_regex_patterns_in_file(file_path)
                    if changes:
                        files_changed += 1
                        total_changes.extend(changes)
                        print(f"\n{file_path}:")
                        for change in changes:
                            print(f"  - {change}")
        except json.JSONDecodeError:
            print("Could not parse ruff output")

    print("\n\nSummary:")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {len(total_changes)}")


if __name__ == "__main__":
    main()
