#!/usr/bin/env python3
"""Script to fix PTH123 (builtin-open) errors by converting to Path.open()."""

import re
from pathlib import Path


def fix_path_open(file_path):
    """Fix PTH123 errors in a single file."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            content = f.read()

        original = content
        lines = content.split("\n")

        # Check if Path is imported
        has_path_import = any(
            "from pathlib import" in line and "Path" in line for line in lines
        )
        needs_path_import = False

        # Pattern to match open() calls
        # Match: with Path(something).open(mode) as f:
        pattern1 = re.compile(
            r'with\s+open\s*\(\s*([^,\)]+)\s*(?:,\s*["\']([^"\']+)["\']\s*)?\)\s+as\s+(\w+)\s*:',
        )

        def replace_open(match):
            nonlocal needs_path_import
            file_var = match.group(1).strip()
            mode = match.group(2) if match.group(2) else "r"
            var_name = match.group(3)

            # Skip if it's stdin/stdout/stderr
            if file_var in ["sys.stdin", "sys.stdout", "sys.stderr"]:
                return match.group(0)

            # Skip if it's a file descriptor (number)
            if file_var.isdigit():
                return match.group(0)

            needs_path_import = True

            # Handle different mode formats
            if mode == "r":
                return f"with Path({file_var}).open() as {var_name}:"
            if mode in ["rb", "r+b", "rb+"]:
                return f'with Path({file_var}).Path("{mode}").open("r") as {var_name}:'
            return f'with Path({file_var}).Path("{mode}").open("r") as {var_name}:'

        # Replace all occurrences
        new_lines = []
        for line in lines:
            if "with Path(" in line:
                new_line = pattern1.sub(replace_open).open(line)
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        # Add Path import if needed and not already present
        if needs_path_import and not has_path_import:
            # Find where to insert the import
            import_index = 0
            for i, line in enumerate(new_lines):
                if line.startswith("import ") or line.startswith("from "):
                    import_index = i + 1
                elif import_index > 0 and line and not line.startswith(" "):
                    # End of import block
                    break

            # Check if pathlib is already imported
            pathlib_imported = False
            pathlib_line = -1
            for i, line in enumerate(new_lines[:import_index]):
                if "from pathlib import" in line:
                    pathlib_imported = True
                    pathlib_line = i
                    break

            if pathlib_imported:
                # Add Path to existing import
                if "Path" not in new_lines[pathlib_line]:
                    if "(" in new_lines[pathlib_line]:
                        # Multi-line import
                        new_lines[pathlib_line] = new_lines[pathlib_line].replace(
                            ")",
                            ", Path)",
                        )
                    else:
                        # Single line import
                        new_lines[pathlib_line] = (
                            new_lines[pathlib_line].rstrip() + ", Path"
                        )
            else:
                # Add new import
                new_lines.insert(import_index, "from pathlib import Path")
                if import_index > 0:
                    new_lines.insert(import_index, "")

        content = "\n".join(new_lines)

        if content != original:
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except (OSError, FileNotFoundError, ImportError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix PTH123 errors in the codebase."""
    # Get all Python files
    files_to_check = []
    for pattern in [
        "chunker/**/*.py",
        "tests/**/*.py",
        "cli/**/*.py",
        "benchmarks/**/*.py",
        "examples/**/*.py",
        "scripts/**/*.py",
    ]:
        files_to_check.extend(Path().glob(pattern))

    fixed = 0
    skipped = 0
    total = 0

    for file_path in files_to_check:
        if "fix_path_operations.py" in str(file_path):
            continue

        # Check if file has open() calls
        try:
            with Path(file_path).open(encoding="utf-8") as f:
                content = f.read()
                if "with open(" in content:
                    total += 1
                    # Skip files that already use Path extensively
                    if (
                        "Path(" in content
                        and content.count("Path(") > content.count("with Path(").open()
                    ):
                        skipped += 1
                        print(f"Skipped (already uses Path): {file_path}")
                        continue

                    if fix_path_open(file_path):
                        print(f"Fixed: {file_path}")
                        fixed += 1
        except (FileNotFoundError, OSError) as e:
            print(f"Error checking {file_path}: {e}")

    print(f"\nFixed {fixed}/{total} files with open() calls")
    print(f"Skipped {skipped} files that already use Path")


if __name__ == "__main__":
    main()
