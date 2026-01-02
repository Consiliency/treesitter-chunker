#!/usr/bin/env python3
"""
Fix indented rows in TOON tabular arrays.

TOON tabular arrays must have rows starting at column 0 (no leading whitespace).
This script removes leading whitespace from tabular array data rows.

Example:
    BEFORE (invalid):
    libraries[3]{id,name}:
      baml,BAML
      mcp,MCP

    AFTER (valid):
    libraries[3]{id,name}:
    baml,BAML
    mcp,MCP
"""

import os
import re
import sys


def process_file(filepath):
    """Process a single TOON file and remove indentation from tabular array rows."""
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    in_tabular_array = False
    modified = False

    for line in lines:
        # Check if this is a tabular array declaration
        # Pattern: name[count]{columns}:
        if re.match(r'^[a-z_]+\[\d+\]\{[^}]+\}:\s*$', line):
            in_tabular_array = True
            new_lines.append(line)
            continue

        # If in tabular array and line is indented, remove indentation
        if in_tabular_array:
            if line.startswith('  ') and not line.strip().startswith('#'):
                # Remove leading whitespace from data row
                new_lines.append(line.lstrip())
                modified = True
            elif line.strip() == '':
                # Blank line ends the array
                in_tabular_array = False
                new_lines.append(line)
            elif not line.startswith(' '):
                # Non-indented content - array ended
                in_tabular_array = False
                new_lines.append(line)
            else:
                # Other indented content (comments, etc)
                new_lines.append(line)
        else:
            new_lines.append(line)

    if modified:
        with open(filepath, 'w') as f:
            f.write('\n'.join(new_lines))
        print(f"Fixed: {filepath}")
        return True
    return False


def walk_dir(root):
    """Walk directory and process all .toon files."""
    fixed_count = 0
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.toon'):
                filepath = os.path.join(dirpath, fname)
                if process_file(filepath):
                    fixed_count += 1
    return fixed_count


def main():
    if len(sys.argv) < 2:
        # Default to ai-docs directory
        target = 'ai-docs'
    else:
        target = sys.argv[1]

    if os.path.isfile(target):
        if process_file(target):
            print(f"Fixed 1 file")
        else:
            print(f"No changes needed: {target}")
    elif os.path.isdir(target):
        count = walk_dir(target)
        print(f"Fixed {count} file(s)")
    else:
        print(f"Error: {target} not found")
        sys.exit(1)


if __name__ == '__main__':
    main()
