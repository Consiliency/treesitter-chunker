#!/usr/bin/env python3
"""Fix import organization more carefully."""

import subprocess
from pathlib import Path


def fix_imports_simple(file_path: Path) -> bool:
    """Fix imports with minimal changes - just move misplaced imports."""
    try:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)

        # Skip files with complex indentation issues
        if any(
            line.strip()
            and not line[0].isspace()
            and not line.startswith(
                (
                    "#",
                    "import",
                    "from",
                    '"""',
                    "'''",
                    "def ",
                    "class ",
                    "@",
                    "if ",
                    "elif ",
                    "else:",
                    "try:",
                    "except",
                    "finally:",
                    "with ",
                    "for ",
                    "while ",
                ),
            )
            for line in lines[10:]
        ):  # Skip first 10 lines which might have module docstring
            # Likely has indentation issues already
            return False

        # Find where imports should go (after module docstring)
        import_insert_line = 0
        in_docstring = False
        docstring_char = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track docstring
            if not in_docstring and (
                stripped.startswith('"""') or stripped.startswith("'''")
            ):
                docstring_char = stripped[:3]
                if stripped.endswith(docstring_char) and len(stripped) > 6:
                    # Single line docstring
                    import_insert_line = i + 1
                    continue
                in_docstring = True
                continue

            if in_docstring and docstring_char in line:
                in_docstring = False
                import_insert_line = i + 1
                continue

            # Stop at first non-docstring, non-comment line
            if not in_docstring and stripped and not stripped.startswith("#"):
                if not stripped.startswith(("import ", "from ")):
                    break

        # Collect misplaced imports (after other code)
        misplaced_imports = []
        first_code_line = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "import ", "from ")):
                if first_code_line is None:
                    first_code_line = i
            elif first_code_line is not None and stripped.startswith(
                ("import ", "from "),
            ):
                # This is a misplaced import
                misplaced_imports.append((i, line))

        if not misplaced_imports:
            return False

        # Remove misplaced imports
        for i, _ in reversed(misplaced_imports):
            del lines[i]

        # Insert them at the correct location
        for _, import_line in reversed(misplaced_imports):
            lines.insert(import_insert_line, import_line)

        # Write back
        new_content = "".join(lines)
        if new_content != content:
            file_path.write_text(new_content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function."""
    repo_root = Path.cwd()

    # Get Python files from git
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    if result.returncode != 0:
        print("Error getting file list from git")
        return

    python_files = [
        repo_root / f.strip()
        for f in result.stdout.splitlines()
        if f.strip() and not f.startswith((".venv", "venv", "build"))
    ]

    fixed_count = 0

    print(f"Processing {len(python_files)} Python files...")

    for file_path in python_files:
        if fix_imports_simple(file_path):
            print(f"Fixed: {file_path}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
