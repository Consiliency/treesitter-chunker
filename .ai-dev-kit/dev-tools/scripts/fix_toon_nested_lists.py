#!/usr/bin/env python3
"""Fix TOON files by adding counts to nested lists that don't have them.

Converts:
  capabilities:
    - item1
    - item2

To:
  capabilities[2]{item}:
    item1
    item2
"""

import os
import re
import sys


def fix_toon_file(filepath):
    """Fix a single TOON file."""
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    modified = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a key with nested list following (indented key without array declaration)
        # Pattern: multiple spaces + key: (no array declaration like [N])
        nested_key_match = re.match(r'^(\s+)([a-z_][a-z0-9_]*):\s*$', line)

        if nested_key_match:
            indent = nested_key_match.group(1)
            key_name = nested_key_match.group(2)
            list_item_indent = indent + '  '

            # Look ahead to see if the next lines are list items
            list_items = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Check for "indent  - item" pattern
                item_match = re.match(rf'^{re.escape(list_item_indent)}- (.+)$', next_line)
                if item_match:
                    list_items.append(item_match.group(1))
                    j += 1
                elif next_line.strip() == '':
                    # Check if more list items follow
                    if j + 1 < len(lines) and re.match(rf'^{re.escape(list_item_indent)}- ', lines[j + 1]):
                        j += 1
                        continue
                    break
                else:
                    break

            if list_items:
                # Found nested list - convert to tabular array
                count = len(list_items)
                new_lines.append(f'{indent}{key_name}[{count}]{{item}}:')
                for item in list_items:
                    new_lines.append(f'{list_item_indent}{item}')
                i = j
                modified = True
                continue

        new_lines.append(line)
        i += 1

    if modified:
        with open(filepath, 'w') as f:
            f.write('\n'.join(new_lines))
        return True
    return False


def process_directory(directory):
    """Process all .toon files in a directory recursively."""
    fixed_count = 0

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.toon'):
                filepath = os.path.join(root, file)
                if fix_toon_file(filepath):
                    print(f"Fixed: {filepath}")
                    fixed_count += 1

    return fixed_count


def main():
    if len(sys.argv) < 2:
        print("Usage: fix_toon_nested_lists.py <file_or_directory>")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isfile(target):
        if fix_toon_file(target):
            print(f"Fixed: {target}")
        else:
            print(f"No changes needed: {target}")
    elif os.path.isdir(target):
        fixed = process_directory(target)
        print(f"\nFixed {fixed} files")
    else:
        print(f"Error: {target} not found")
        sys.exit(1)


if __name__ == '__main__':
    main()
