#!/usr/bin/env python3
"""Fix import organization errors (PLC0415, E402)."""

import subprocess
from pathlib import Path


def organize_imports(file_path: Path) -> bool:
    """Organize imports in a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Skip files that start with shebang or encoding
        skip_lines = 0
        if lines and lines[0].startswith("#!"):
            skip_lines = 1
        if len(lines) > skip_lines and lines[skip_lines].startswith("# -*- coding"):
            skip_lines += 1

        # Find docstring if exists
        docstring_end = skip_lines
        if len(lines) > skip_lines:
            # Check for module docstring
            stripped = lines[skip_lines].strip()
            if stripped.startswith(('"""', "'''")):
                quote = stripped[:3]
                if stripped.endswith(quote) and len(stripped) > 6:
                    # Single line docstring
                    docstring_end = skip_lines + 1
                else:
                    # Multi-line docstring
                    for i in range(skip_lines + 1, len(lines)):
                        if quote in lines[i]:
                            docstring_end = i + 1
                            break

        # Collect all imports
        future_imports = []
        standard_imports = []
        third_party_imports = []
        local_imports = []
        non_import_lines = []

        # Standard library modules
        stdlib_modules = {
            "abc",
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "collections",
            "concurrent",
            "contextlib",
            "copy",
            "datetime",
            "decimal",
            "enum",
            "functools",
            "gc",
            "hashlib",
            "http",
            "importlib",
            "inspect",
            "io",
            "itertools",
            "json",
            "logging",
            "math",
            "multiprocessing",
            "os",
            "pathlib",
            "pickle",
            "platform",
            "queue",
            "re",
            "shutil",
            "socket",
            "subprocess",
            "sys",
            "tempfile",
            "textwrap",
            "threading",
            "time",
            "traceback",
            "typing",
            "unittest",
            "urllib",
            "uuid",
            "warnings",
            "weakref",
            "xml",
            "zipfile",
        }

        i = docstring_end
        found_non_import = False

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines and comments between imports
            if not stripped or stripped.startswith("#"):
                if not found_non_import:
                    i += 1
                    continue
                non_import_lines.append(line)
            elif stripped.startswith("from __future__"):
                future_imports.append(line)
            elif stripped.startswith(("import ", "from ")):
                if found_non_import:
                    # Import after non-import code - this is E402
                    # Move it to the import section
                    pass

                # Determine import type
                if stripped.startswith(("from .", "from ..")):
                    local_imports.append(line)
                else:
                    # Extract module name
                    if stripped.startswith("import "):
                        module = stripped.split()[1].split(".")[0].split(",")[0]
                    else:
                        module = stripped.split()[1].split(".")[0]

                    if module in stdlib_modules:
                        standard_imports.append(line)
                    elif module.startswith("chunker"):
                        local_imports.append(line)
                    else:
                        third_party_imports.append(line)
            else:
                # Non-import line
                found_non_import = True
                non_import_lines.append(line)

            i += 1

        # Sort imports within each group
        future_imports.sort()
        standard_imports.sort()
        third_party_imports.sort()
        local_imports.sort()

        # Reconstruct file
        new_lines = lines[:docstring_end]

        # Add blank line after docstring if needed
        if (
            docstring_end > skip_lines
            and (
                future_imports
                or standard_imports
                or third_party_imports
                or local_imports
            )
            and new_lines
            and new_lines[-1].strip() != ""
        ):
            new_lines.append("\n")

        # Add imports in order
        if future_imports:
            new_lines.extend(future_imports)
            new_lines.append("\n")

        if standard_imports:
            new_lines.extend(standard_imports)
            if third_party_imports or local_imports:
                new_lines.append("\n")

        if third_party_imports:
            new_lines.extend(third_party_imports)
            if local_imports:
                new_lines.append("\n")

        if local_imports:
            new_lines.extend(local_imports)

        # Add blank line before non-import code
        if (
            (future_imports or standard_imports or third_party_imports or local_imports)
            and non_import_lines
            and new_lines
            and new_lines[-1].strip() != ""
        ):
            new_lines.append("\n")

        # Add remaining code
        new_lines.extend(non_import_lines)

        new_content = "".join(new_lines)

        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            return True
        return False

    except (OSError, FileNotFoundError, ImportError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix import organization."""
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
    total_files = len(python_files)

    print(f"Processing {total_files} Python files...")

    for i, file_path in enumerate(python_files):
        if i % 50 == 0 and i > 0:
            print(f"Progress: {i}/{total_files} files processed")

        if organize_imports(file_path):
            print(f"Fixed: {file_path}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
