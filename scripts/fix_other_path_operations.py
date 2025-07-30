#!/usr/bin/env python3
"""Fix other path operation errors (PTH108, PTH118, PTH101)."""

import re
import subprocess
from pathlib import Path


def fix_path_operations(file_path: Path) -> bool:
    """Fix various path operations to use pathlib."""
    try:
        content = file_path.read_text()
        original_content = content
        lines = content.splitlines(keepends=True)

        # Track if Path needs to be imported
        needs_path_import = False
        has_path_import = any(
            "from pathlib import" in line and "Path" in line for line in lines
        )

        # PTH118: os.path.join() -> Path() with / operator
        join_pattern = r"os\.path\.join\((.*?)\)"

        def replace_join(match):
            nonlocal needs_path_import
            args = match.group(1)
            # Handle simple cases
            if "," in args:
                parts = [arg.strip() for arg in args.split(",")]
                if len(parts) == 2:
                    needs_path_import = True
                    return f"Path({parts[0]}) / {parts[1]}"
                # Multiple parts
                needs_path_import = True
                result = f"Path({parts[0]})"
                for part in parts[1:]:
                    result += f" / {part}"
                return result
            return match.group(0)

        content = re.sub(join_pattern, replace_join, content)

        # PTH108: os.path.dirname() -> Path().parent
        dirname_pattern = r"os\.path\.dirname\((.*?)\)"

        def replace_dirname(match):
            nonlocal needs_path_import
            arg = match.group(1).strip()
            needs_path_import = True
            return f"Path({arg}).parent"

        content = re.sub(dirname_pattern, replace_dirname, content)

        # PTH101: os.path.exists() -> Path().exists()
        exists_pattern = r"os\.path\.exists\((.*?)\)"

        def replace_exists(match):
            nonlocal needs_path_import
            arg = match.group(1).strip()
            needs_path_import = True
            return f"Path({arg}).exists()"

        content = re.sub(exists_pattern, replace_exists, content)

        # Also handle os.path.isfile() -> Path().is_file()
        isfile_pattern = r"os\.path\.isfile\((.*?)\)"

        def replace_isfile(match):
            nonlocal needs_path_import
            arg = match.group(1).strip()
            needs_path_import = True
            return f"Path({arg}).is_file()"

        content = re.sub(isfile_pattern, replace_isfile, content)

        # Also handle os.path.isdir() -> Path().is_dir()
        isdir_pattern = r"os\.path\.isdir\((.*?)\)"

        def replace_isdir(match):
            nonlocal needs_path_import
            arg = match.group(1).strip()
            needs_path_import = True
            return f"Path({arg}).is_dir()"

        content = re.sub(isdir_pattern, replace_isdir, content)

        # Also handle os.path.abspath() -> Path().resolve()
        abspath_pattern = r"os\.path\.abspath\((.*?)\)"

        def replace_abspath(match):
            nonlocal needs_path_import
            arg = match.group(1).strip()
            needs_path_import = True
            return f"Path({arg}).resolve()"

        content = re.sub(abspath_pattern, replace_abspath, content)

        # Handle os.makedirs() -> Path().mkdir()
        makedirs_pattern = r"os\.makedirs\((.*?)\)"

        def replace_makedirs(match):
            nonlocal needs_path_import
            full_match = match.group(0)
            args = match.group(1)

            # Check for exist_ok parameter
            if "exist_ok" in args:
                path_arg = args.split(",")[0].strip()
                needs_path_import = True
                return f"Path({path_arg}).mkdir(parents=True, exist_ok=True)"
            needs_path_import = True
            return f"Path({args}).mkdir(parents=True)"

        content = re.sub(makedirs_pattern, replace_makedirs, content)

        # If we made changes and need Path import, add it
        if needs_path_import and not has_path_import and content != original_content:
            lines = content.splitlines(keepends=True)

            # Find where to insert import
            import_line = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith("#"):
                    # Skip module docstring
                    if line.strip().startswith('"""') or line.strip().startswith("'''"):
                        # Find end of docstring
                        quote = line.strip()[:3]
                        if line.strip().endswith(quote) and len(line.strip()) > 6:
                            import_line = i + 1
                        else:
                            for j in range(i + 1, len(lines)):
                                if quote in lines[j]:
                                    import_line = j + 1
                                    break
                    elif line.startswith("import ") or line.startswith("from "):
                        # Check if we have pathlib import already
                        if "pathlib" in line:
                            if "Path" not in line:
                                # Add Path to existing pathlib import
                                lines[i] = line.rstrip() + ", Path\n"
                                has_path_import = True
                                break
                        continue
                    else:
                        # First non-import line
                        break

            # Add import if still needed
            if not has_path_import and needs_path_import:
                if any("pathlib" in line for line in lines):
                    # Already has pathlib import, just need to add Path
                    for i, line in enumerate(lines):
                        if "from pathlib import" in line and "Path" not in line:
                            lines[i] = line.rstrip().rstrip("\n")
                            if line.rstrip().endswith(")"):
                                lines[i] = lines[i][:-1] + ", Path)\n"
                            else:
                                lines[i] = lines[i] + ", Path\n"
                            break
                else:
                    # Need to add new import
                    lines.insert(import_line, "from pathlib import Path\n")
                    if import_line > 0 and lines[import_line - 1].strip():
                        lines.insert(import_line, "\n")

            content = "".join(lines)

        if content != original_content:
            file_path.write_text(content)
            return True
        return False

    except (OSError, FileNotFoundError, ImportError) as e:
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
    total_files = len(python_files)

    print(f"Processing {total_files} Python files...")

    for i, file_path in enumerate(python_files):
        if i % 50 == 0 and i > 0:
            print(f"Progress: {i}/{total_files} files processed")

        if fix_path_operations(file_path):
            print(f"Fixed: {file_path}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
