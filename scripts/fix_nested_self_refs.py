#!/usr/bin/env python3
"""Fix undefined 'self' references in nested functions."""

import re
from pathlib import Path


def fix_nested_self_refs(file_path: Path) -> list[str]:
    """Fix nested functions trying to access self from staticmethods."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Pattern to find @staticmethod followed by a method that has nested functions using self
    lines = content.split("\n")
    fixed_lines = []
    method_indent = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if we're starting a staticmethod
        if "@staticmethod" in stripped:
            # Look ahead to see if the method uses self in nested functions
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1

            if j < len(lines) and "def " in lines[j]:
                # Get the method definition
                method_line = lines[j]
                method_indent = len(method_line) - len(method_line.lstrip())

                # Check if any nested function uses self
                has_nested_self = False
                k = j + 1
                while k < len(lines):
                    current_indent = len(lines[k]) - len(lines[k].lstrip())
                    if current_indent <= method_indent and lines[k].strip():
                        break
                    if "self." in lines[k] or "self[" in lines[k]:
                        # Check if it's in a nested function
                        nested_func_indent = None
                        m = k - 1
                        while m > j:
                            if (
                                "def " in lines[m]
                                and len(lines[m]) - len(lines[m].lstrip())
                                > method_indent
                            ):
                                nested_func_indent = len(lines[m]) - len(
                                    lines[m].lstrip(),
                                )
                                break
                            m -= 1
                        if nested_func_indent is not None:
                            has_nested_self = True
                            break
                    k += 1

                if has_nested_self:
                    # Remove @staticmethod and add self parameter
                    changes.append("Removed @staticmethod and added self parameter")
                    # Skip the @staticmethod line
                    i += 1
                    # Update the method definition to include self
                    while i < len(lines) and "def " not in lines[i]:
                        fixed_lines.append(lines[i])
                        i += 1
                    if i < len(lines):
                        method_def = lines[i]
                        # Add self parameter if not present
                        if "(self" not in method_def:
                            if "()" in method_def:
                                method_def = method_def.replace("()", "(self)")
                            else:
                                # Insert self as first parameter
                                match = re.match(
                                    r"(\s*def\s+\w+\s*\()(.+?)(\)\s*(?:->.*)?:)",
                                    method_def,
                                )
                                if match:
                                    method_def = f"{match.group(1)}self, {match.group(2)}{match.group(3)}"
                        fixed_lines.append(method_def)
                        i += 1
                    continue

        fixed_lines.append(line)
        i += 1

    if changes:
        new_content = "\n".join(fixed_lines)
        if new_content != original:
            file_path.write_text(new_content, encoding="utf-8")
            return changes

    return []


def main():
    """Main function."""
    # Find all Python files with F821 errors related to self
    project_root = Path(__file__).parent.parent

    files_to_fix = [
        project_root / "chunker/debug/visualization/ast_visualizer.py",
        project_root / "chunker/fallback/sliding_window_fallback.py",
        project_root / "chunker/repo/metadata_extractor.py",
        project_root / "chunker/repo/relationship_tracker.py",
        project_root / "chunker/strategies/hierarchical.py",
        project_root / "chunker/strategies/semantic.py",
        project_root / "chunker/strategies/adaptive.py",
    ]

    total_changes = []

    for file_path in files_to_fix:
        if file_path.exists():
            changes = fix_nested_self_refs(file_path)
            if changes:
                print(f"\n{file_path}:")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal fixes: {len(total_changes)}")


if __name__ == "__main__":
    main()
