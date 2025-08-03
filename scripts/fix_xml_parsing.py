#!/usr/bin/env python3
"""Fix S314 - Add noqa comments for XML parsing in tests."""

import re
from pathlib import Path


def fix_xml_parsing_in_file(file_path: Path) -> list[str]:
    """Fix XML parsing warnings in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    changes = []

    # Pattern to find ET.fromstring() calls
    pattern1 = r"(\s*)(root = ET\.fromstring\(xml_str\))"
    replacement1 = r"\1\2  # noqa: S314 - Parsing test-generated XML"

    # Pattern to find ET.parse() calls
    pattern2 = r"(\s*)(tree = ET\.parse\([^)]+\))"
    replacement2 = r"\1\2  # noqa: S314 - Parsing test-generated XML"

    # Pattern for standalone ET.fromstring
    pattern3 = r"(\s*)(ET\.fromstring\(xml_str\))"
    replacement3 = r"\1\2  # noqa: S314 - Parsing test-generated XML"

    # Apply replacements
    new_content = content

    # Count changes for each pattern
    for pattern, replacement in [(pattern1, replacement1), (pattern2, replacement2), (pattern3, replacement3)]:
        matches = re.findall(pattern, new_content)
        if matches:
            new_content = re.sub(pattern, replacement, new_content)
            changes.append(f"Added noqa comment to {len(matches)} XML parsing calls")

    if new_content != original_content:
        file_path.write_text(new_content, encoding="utf-8")
        return changes

    return []


def main():
    """Main function."""
    # Files with S314 errors
    files_to_fix = [
        Path("/home/jenner/code/treesitter-chunker/tests/test_graphml_exporter.py"),
        Path("/home/jenner/code/treesitter-chunker/tests/test_phase12_integration.py"),
    ]

    total_changes = []

    for file_path in files_to_fix:
        if file_path.exists():
            print(f"\nChecking {file_path}...")
            changes = fix_xml_parsing_in_file(file_path)
            if changes:
                print(f"Fixed XML parsing in {file_path}")
                for change in changes:
                    print(f"  - {change}")
                total_changes.extend(changes)

    print(f"\n\nTotal changes: {len(total_changes)}")


if __name__ == "__main__":
    main()
