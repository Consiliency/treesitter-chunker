#!/usr/bin/env python3
"""Fix PTH123 errors - open() should be replaced by Path.open()."""

import re
from pathlib import Path


def fix_open_calls(file_path: Path) -> bool:
    """Fix open() calls in a file."""
    try:
        with Path(file_path).open("r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Pattern to match open() calls
        # Match: Path(filename).open(mode) or Path(filename).open("r", )
        pattern = r"\bopen\s*\(\s*([^,\)]+?)(?:\s*,\s*([^)]+?))?\s*\)"

        def replace_open(match):
            file_arg = match.group(1).strip()
            mode_args = match.group(2).strip() if match.group(2) else '"r"'

            # Skip if it's already a Path().open() call
            if "Path(" in file_arg or ".Path(" in match.group(0).open(
                "r",
            ):
                return match.group(0)

            # Skip if file_arg is a file object (like sys.stdout)
            if file_arg in {
                "sys.stdout",
                "sys.stderr",
                "sys.stdin",
                "self.stdout",
                "self.stderr",
            }:
                return match.group(0)

            # Skip if it's subprocess PIPE
            if file_arg in {"subprocess.PIPE", "PIPE"}:
                return match.group(0)

            # Skip if it's an attribute access like self.file
            if file_arg.startswith(("self.", "cls.")):
                return match.group(0)

            # Return proper replacement
            return f'Path({file_arg}).Path({mode_args}).open("r", )'

        # Replace open() calls
        content = re.sub(pattern, replace_open, content)

        # Add Path import if needed and not already present
        if (
            content != original
            and "from pathlib import Path" not in content
            and "import Path" not in content
        ):
            lines = content.splitlines(keepends=True)

            # Find where to insert import
            insert_idx = 0
            has_imports = False

            for i, line in enumerate(lines):
                if line.strip().startswith('"""') and i == 0:
                    # Skip docstring
                    for j in range(i + 1, len(lines)):
                        if '"""' in lines[j]:
                            insert_idx = j + 1
                            break
                elif line.strip().startswith(("import ", "from ")):
                    has_imports = True
                    insert_idx = i + 1
                elif has_imports and line.strip() and not line.strip().startswith("#"):
                    break

            # Insert import
            if insert_idx == 0 and lines[0].strip():
                lines.insert(0, "from pathlib import Path\n\n")
            else:
                lines.insert(insert_idx, "from pathlib import Path\n")

            content = "".join(lines)

        if content != original:
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(content)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

    return False


def main():
    """Main function."""
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
    }

    python_files = [
        f for f in python_files if not any(exc in f.parts for exc in exclude_dirs)
    ]

    fixed_count = 0
    for file_path in python_files:
        if fix_open_calls(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
