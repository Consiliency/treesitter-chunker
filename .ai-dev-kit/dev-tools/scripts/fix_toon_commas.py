#!/usr/bin/env python3
"""Fix TOON files by quoting values with commas in tabular arrays.

This script:
1. Detects tabular array declarations (e.g., sections[4]{id,name,path,page_count,when_to_use}:)
2. For each data row, if there are more values than expected columns,
   it assumes the extra commas are in the LAST column and quotes that field
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

    # Track current tabular array context
    current_array_cols = 0
    in_tabular_array = False

    for line in lines:
        # Check for tabular array declaration: key[N]{col1,col2,...}:
        array_match = re.match(r'^([a-z_]+)\[(\d+)\]\{([^}]+)\}:\s*$', line)
        if array_match:
            cols = array_match.group(3).split(',')
            current_array_cols = len(cols)
            in_tabular_array = True
            new_lines.append(line)
            continue

        # Check if we're in a tabular array (indented row)
        if in_tabular_array:
            # Check if this is a data row (starts with 2 spaces, not empty, not a new key)
            if line.startswith('  ') and line.strip() and not re.match(r'^  [a-z_]+:', line):
                row_content = line[2:]  # Remove the 2-space indent

                # Count commas to detect if we have too many values
                # Simple CSV-like parsing (doesn't handle quoted values yet)
                values = parse_csv_row(row_content)

                if len(values) > current_array_cols:
                    # Too many values - need to quote the excess in the last column
                    # Join the excess values back together for the last column
                    fixed_values = values[:current_array_cols - 1]
                    last_value = ','.join(values[current_array_cols - 1:])

                    # Quote the last value if it contains commas
                    if ',' in last_value:
                        # Replace commas with semicolons in the last value (safer than quoting)
                        last_value = last_value.replace(',', ';')

                    fixed_values.append(last_value)
                    new_line = '  ' + ','.join(fixed_values)
                    new_lines.append(new_line)
                    modified = True
                    continue
            elif not line.startswith('  ') and line.strip():
                # Non-indented line means we've exited the tabular array
                in_tabular_array = False
            elif line.strip() == '':
                # Blank line ends array
                in_tabular_array = False

        new_lines.append(line)

    if modified:
        with open(filepath, 'w') as f:
            f.write('\n'.join(new_lines))
        return True
    return False


def parse_csv_row(row):
    """Parse a CSV-like row, respecting quoted values."""
    values = []
    current = ''
    in_quotes = False
    quote_char = None

    i = 0
    while i < len(row):
        char = row[i]

        if char in '"\'':
            if not in_quotes:
                in_quotes = True
                quote_char = char
                current += char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
                current += char
            else:
                current += char
        elif char == ',' and not in_quotes:
            values.append(current)
            current = ''
        else:
            current += char

        i += 1

    # Don't forget the last value
    if current:
        values.append(current)

    return values


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
        print("Usage: fix_toon_commas.py <file_or_directory>")
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
