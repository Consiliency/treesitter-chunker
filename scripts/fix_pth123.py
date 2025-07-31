#!/usr/bin/env python3
"""Fix PTH123 - Replace open() with Path.open()."""

import re
from pathlib import Path


def fix_pth123_in_file(file_path: Path) -> bool:
    """Fix PTH123 issues in a file."""
    try:
        with Path(file_path).open("r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    original_content = content

    # Check if pathlib is imported
    has_path_import = "from pathlib import Path" in content
    has_pathlib_import = "import pathlib" in content

    # Pattern 1: Path(file_path).open() where file_path is a variable
    pattern1 = re.compile(
        r"\bopen\s*\(\s*([a-zA-Z_]\w*)\s*(?:,([^)]*))?\)",
        re.MULTILINE,
    )

    def replace_open_var(match):
        var_name = match.group(1)
        args = match.group(2) if match.group(2) else ""

        # Skip if it looks like it's already a Path object
        if "Path(" in content[: match.start()]:
            return match.group(0)

        if args:
            return f"Path({var_name}).open({args})"
        return f"Path({var_name}).open()"

    # Pattern 2: Path("string_literal").open() or Path('string_literal').open()
    pattern2 = re.compile(
        r'\bopen\s*\(\s*(["\'])([^"\']+)\1\s*(?:,([^)]*))?\)',
        re.MULTILINE,
    )

    def replace_open_literal(match):
        quote = match.group(1)
        path_str = match.group(2)
        args = match.group(3) if match.group(3) else ""

        if args:
            return f"Path({quote}{path_str}{quote}).open({args})"
        return f"Path({quote}{path_str}{quote}).open()"

    # Pattern 3: with Path(...).open() as f:
    pattern3 = re.compile(
        r"with\s+open\s*\(\s*([^)]+)\)\s*as\s+(\w+)\s*:",
        re.MULTILINE,
    )

    def replace_with_open(match):
        args = match.group(1).strip()
        var_name = match.group(2)

        # Check if first arg is quoted string
        if args.startswith(('"', "'")):
            quote = args[0]
            end_quote = args.find(quote, 1)
            if end_quote > 0:
                path_part = args[: end_quote + 1]
                rest = args[end_quote + 1 :].strip()
                if rest.startswith(","):
                    rest = rest[1:].strip()
                    return f"with Path({path_part}).open({rest}) as {var_name}:"
                return f"with Path({path_part}).open() as {var_name}:"

        # It's a variable
        parts = args.split(",", 1)
        path_var = parts[0].strip()
        if len(parts) > 1:
            return f"with Path({path_var}).open({parts[1]}) as {var_name}:"
        return f"with Path({path_var}).open() as {var_name}:"

    # Apply replacements
    content = pattern1.sub(replace_open_var, content)
    content = pattern2.sub(replace_open_literal, content)
    content = pattern3.sub(replace_with_open, content)

    # Add Path import if needed and not already present
    if content != original_content and not has_path_import and not has_pathlib_import:
        # Find the right place to add import
        import_lines = []
        lines = content.split("\n")
        insert_pos = 0

        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")):
                insert_pos = i + 1
            elif line and not line.startswith("#") and insert_pos > 0:
                break

        if insert_pos == 0:
            # No imports found, add at the beginning
            content = "from pathlib import Path\n\n" + content
        else:
            lines.insert(insert_pos, "from pathlib import Path")
            content = "\n".join(lines)

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
    """Main function to fix PTH123 issues."""
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
        if fix_pth123_in_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
