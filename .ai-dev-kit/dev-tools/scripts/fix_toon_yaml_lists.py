#!/usr/bin/env python3
"""Fix TOON files by converting YAML-style lists to tabular arrays.

Converts:
  key:
    - item1
    - item2

To:
  key[2]{item}:
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

        # Check if this is a key that might have a YAML list following
        # Pattern: key: (with nothing after, or just whitespace)
        key_match = re.match(r'^([a-z_][a-z0-9_]*):\s*$', line)

        if key_match:
            key_name = key_match.group(1)

            # Look ahead to see if the next lines are YAML list items
            list_items = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Check for "  - item" pattern
                item_match = re.match(r'^  - (.+)$', next_line)
                if item_match:
                    list_items.append(item_match.group(1))
                    j += 1
                elif next_line.strip() == '':
                    # Empty line - might be end of list or just spacing
                    # Check if there are more list items after
                    if j + 1 < len(lines) and re.match(r'^  - ', lines[j + 1]):
                        j += 1
                        continue
                    break
                else:
                    # Non-list line - end of list
                    break

            if list_items:
                # Found YAML list - convert to tabular array
                count = len(list_items)
                new_lines.append(f'{key_name}[{count}]{{item}}:')
                for item in list_items:
                    new_lines.append(f'  {item}')
                i = j
                modified = True
                continue

        # Also check for numbered list pattern:
        # key:
        #   1. item1
        #   2. item2
        numbered_key_match = re.match(r'^([a-z_][a-z0-9_]*):\s*$', line)
        if numbered_key_match:
            key_name = numbered_key_match.group(1)

            # Look ahead for numbered items
            list_items = []
            j = i + 1
            expected_num = 1
            while j < len(lines):
                next_line = lines[j]
                # Check for "  N. item" pattern
                num_match = re.match(r'^  (\d+)\. (.+)$', next_line)
                if num_match:
                    list_items.append(num_match.group(2))
                    expected_num += 1
                    j += 1
                elif next_line.strip() == '':
                    # Check if more numbered items follow
                    if j + 1 < len(lines) and re.match(r'^  \d+\. ', lines[j + 1]):
                        j += 1
                        continue
                    break
                else:
                    break

            if len(list_items) > 1:
                # Convert numbered list to tabular array
                count = len(list_items)
                new_lines.append(f'{key_name}[{count}]{{step}}:')
                for item in list_items:
                    new_lines.append(f'  {item}')
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
        print("Usage: fix_toon_yaml_lists.py <file_or_directory>")
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
