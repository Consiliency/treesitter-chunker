#!/usr/bin/env python3
"""Fix @staticmethod + @property combination errors."""

import re
from pathlib import Path


def fix_property_decorators(file_path: Path) -> list[str]:
    """Fix invalid @staticmethod + @property combinations."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Pattern to find @staticmethod followed by @property
    pattern = r"(\s*)@staticmethod\s*\n\s*@property\s*\n(\s*def\s+\w+\([^)]*\)\s*->\s*[^:]+:)"

    def replace_decorators(match):
        indent = match.group(1)
        func_def = match.group(2)

        # Add self parameter if not present
        if ("(self" not in func_def and "()" in func_def) or "()" in func_def:
            func_def = func_def.replace("()", "(self)")

        changes.append("Fixed @staticmethod + @property combination")
        return f"{indent}@property\n{func_def}"

    content = re.sub(pattern, replace_decorators, content, flags=re.MULTILINE)

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    # Find all language files
    project_root = Path(__file__).parent.parent
    language_files = list((project_root / "chunker" / "languages").glob("*.py"))

    # Also check other files that might have this issue
    other_dirs = [
        project_root / "chunker" / "fallback",
        project_root / "chunker" / "context" / "languages",
        project_root / "tests",
    ]

    for dir_path in other_dirs:
        if dir_path.exists():
            language_files.extend(dir_path.rglob("*.py"))

    print(f"Checking {len(language_files)} files for @staticmethod + @property issues...")

    total_changes = []

    for file_path in language_files:
        changes = fix_property_decorators(file_path)
        if changes:
            print(f"\n{file_path}:")
            for change in changes:
                print(f"  - {change}")
            total_changes.extend(changes)

    print(f"\n\nTotal fixes: {len(total_changes)}")


if __name__ == "__main__":
    main()
