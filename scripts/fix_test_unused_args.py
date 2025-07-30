#!/usr/bin/env python3
"""Fix unused arguments in test files by documenting them."""

import re
from pathlib import Path


def fix_test_file(file_path: Path) -> bool:
    """Fix unused arguments in test files by adding comments."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            lines = f.readlines()

        modified = False

        # Simple approach: look for common test patterns and add del statements
        for i, line in enumerate(lines):
            # Match function definitions with common test fixture names
            match = re.match(
                r"^(\s*)def\s+test_\w+\([^)]*\b(tmp_path|temp_dir|capsys|caplog|monkeypatch|mock_\w+|fixture_\w+)\b[^)]*\):",
                line,
            )
            if match:
                indent = match.group(1)
                # Check if next line is already a del statement or docstring
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not (next_line.startswith(('"""', "'''", "del "))):
                        # Look for fixture names in the function signature
                        fixtures = re.findall(
                            r"\b(tmp_path|temp_dir|capsys|caplog|monkeypatch|mock_\w+|fixture_\w+)\b",
                            line,
                        )
                        if fixtures:
                            # Add del statement for fixtures
                            del_line = f"{indent}    del {', '.join(set(fixtures))}  # unused fixtures\n"
                            lines.insert(i + 1, del_line)
                            modified = True

        if modified:
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Fixed {file_path}")
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return False


def main():
    """Main function."""
    # Get test files
    test_files = []
    for pattern in ["**/test_*.py", "**/*_test.py"]:
        test_files.extend(Path().glob(pattern))

    # Also get files in tests directories
    for tests_dir in Path().glob("**/tests"):
        if tests_dir.is_dir():
            test_files.extend(tests_dir.glob("**/*.py"))

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
    }

    test_files = [
        f for f in test_files if not any(exc in f.parts for exc in exclude_dirs)
    ]

    # Remove duplicates
    test_files = list(set(test_files))

    fixed_count = 0
    for file_path in test_files:
        if fix_test_file(file_path):
            fixed_count += 1

    print(f"\nFixed {fixed_count} test files")


if __name__ == "__main__":
    main()
