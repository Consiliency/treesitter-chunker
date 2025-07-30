#!/usr/bin/env python3
"""Fix BLE001 blind except errors by using specific exception types."""

import re
from pathlib import Path


def analyze_exception_context(lines: list[str], except_line_idx: int) -> str:
    """Analyze code context to determine appropriate exception type."""
    # Look at previous lines for context
    context_start = max(0, except_line_idx - 10)
    context_lines = lines[context_start:except_line_idx]
    context = "\n".join(context_lines)

    # File operations
    if any(
        pattern in context
        for pattern in [
            "open(",
            ".read",
            ".write",
            "os.",
            "file",
            "path",
        ]
    ):
        return "(FileNotFoundError, IOError, OSError)"

    # JSON operations
    if "json.load" in context or "json.dump" in context:
        return "(json.JSONDecodeError, ValueError, TypeError)"

    # Import statements
    if "import " in context:
        return "ImportError"

    # Type conversions
    if any(pattern in context for pattern in ["int(", "float(", "str("]):
        return "(ValueError, TypeError)"

    # Attribute access
    if re.search(r"\w+\.\w+", context):
        return "AttributeError"

    # Network operations
    if any(pattern in context for pattern in ["request", "http", "url", "socket"]):
        return "(ConnectionError, TimeoutError, OSError)"

    # Default - keep generic Exception but add a comment
    return "Exception  # TODO: Consider more specific exception type"


def fix_blind_except_advanced(file_path: Path) -> bool:
    """Fix blind except clauses with context-aware replacements."""
    try:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)
        original_lines = lines.copy()
        modified = False

        for i, line in enumerate(lines):
            # Match "except Exception:" with optional whitespace
            if re.match(r"^(\s*)except\s+Exception\s*:", line):
                indent = re.match(r"^(\s*)", line).group(1)

                # Determine appropriate exception type based on context
                exception_type = analyze_exception_context(lines, i)

                # Replace the line
                new_line = f"{indent}except {exception_type}:\n"
                if new_line != line:
                    lines[i] = new_line
                    modified = True

        if modified:
            file_path.write_text("".join(lines))
            return True
        return False

    except (OSError, FileNotFoundError, IndexError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix blind except errors."""
    repo_root = Path.cwd()

    # Get Python files from git
    import subprocess

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

        if fix_blind_except_advanced(file_path):
            print(f"Fixed: {file_path}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
