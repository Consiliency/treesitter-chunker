#!/usr/bin/env python3
"""Script to fix SIM102 (collapsible if statements) errors."""

import re
from pathlib import Path


def fix_sim102_in_file(file_path):
    """Fix SIM102 errors in a single file."""
    try:
        with Path(file_path).open(
            "r", encoding="utf-8",
        ) as f:
            content = f.read()

        original = content

        # Pattern 1: Simple nested if
        # if condition1:
        #     if condition2:
        #         action
        pattern1 = re.compile(
            r"(\s*)if\s+(.+?):\s*\n\1    if\s+(.+?):\s*\n(\1        .+)",
            re.MULTILINE,
        )

        def replace1(match):
            indent = match.group(1)
            cond1 = match.group(2).strip()
            cond2 = match.group(3).strip()
            action = match.group(4)

            # Don't combine if there are comments between
            if "#" in match.group(0).split("\n")[1]:
                return match.group(0)

            return f"{indent}if {cond1} and {cond2}:\n{action}"

        content = pattern1.sub(replace1, content)

        # Pattern 2: With comment between
        # if condition1:
        #     # comment
        #     if condition2:
        re.compile(
            r"(\s*)if\s+(.+?):\s*\n"
            r"(\1    #.*\n)?"  # Optional comment
            r"\1    if\s+(.+?):\s*\n",
            re.MULTILINE,
        )

        # Pattern 3: More complex conditions already with 'and'
        # if cond1 and cond2:
        #     if cond3:
        pattern3 = re.compile(
            r"(\s*)if\s+(.+?)\s+and\s+(.+?):\s*\n"
            r"(?:\1    #.*\n)?"  # Optional comment
            r"\1    if\s+(.+?):\s*\n",
            re.MULTILINE,
        )

        def replace3(match):
            indent = match.group(1)
            cond1 = match.group(2).strip()
            cond2 = match.group(3).strip()
            cond3 = match.group(4).strip()
            return f"{indent}if {cond1} and {cond2} and {cond3}:\n"

        content = pattern3.sub(replace3, content)

        if content != original:
            with Path(file_path).open(
                "w", encoding="utf-8",
            ) as f:
                f.write(content)
            return True
        return False

    except (OSError, FileNotFoundError, IndexError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix SIM102 errors in the codebase."""
    # Files with SIM102 errors from ruff output
    files_to_fix = [
        "chunker/auto.py",
        "chunker/cicd/workflow_validator.py",
        "chunker/context/filter.py",
        "chunker/context/languages/python.py",
        "chunker/context/symbol_resolver.py",
        "chunker/export/relationships/tracker.py",
        "chunker/fallback/line_based.py",
        "chunker/fallback/sliding_window_fallback.py",
        "chunker/grammar/builder.py",
        "chunker/grammar/manager.py",
        "chunker/grammar_manager.py",
        "chunker/multi_language.py",
        "chunker/plugin_manager.py",
        "chunker/processors/config.py",
        "chunker/processors/logs.py",
        "chunker/repo/processor.py",
        "chunker/strategies/composite.py",
        "chunker/strategies/hierarchical.py",
        "chunker/strategies/semantic.py",
        "chunker/token/chunker.py",
        "chunker/vfs.py",
        "cli/main.py",
        "tests/test_composite_chunker.py",
        "tests/test_hierarchical_chunker.py",
    ]

    fixed = 0
    for file_path in files_to_fix:
        full_path = Path(file_path)
        if full_path.exists():
            if fix_sim102_in_file(full_path):
                print(f"Fixed: {file_path}")
                fixed += 1
        else:
            print(f"Not found: {file_path}")

    print(f"\nFixed {fixed} files")


if __name__ == "__main__":
    main()
