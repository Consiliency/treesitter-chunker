#!/usr/bin/env python3
"""
Remove comment lines from TOON files.

The TOON CLI (@toon-format/cli) does NOT support comments.
Lines starting with # are parsed as keys without colons, causing errors.

This script removes all lines that start with # (comment lines).
"""

import os
import sys


def process_file(filepath):
    """Process a single TOON file and remove comment lines."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    modified = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('#'):
            # Skip comment lines
            modified = True
        else:
            new_lines.append(line)

    if modified:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
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
