import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []

    # Regex to capture: indent, key, count, separator, values
    # e.g. "  key_concepts[5]: a|b|c"
    # Matches: "  ", "key_concepts", "5", ":", " a|b|c"
    # We require at least one pipe to consider it a candidate for fix

    array_pattern = re.compile(r'^(\s*)([^\[]+)\[(\d+)\]:\s*(.+)$')

    for line in lines:
        match = array_pattern.match(line)
        if match:
            indent = match.group(1)
            key = match.group(2)
            count = match.group(3)
            content = match.group(4)

            # Check if it looks like a pipe-delimited array
            if '|' in content and not content.strip().startswith(('"', '{')):
                # It has pipes and doesn't look like a quoted string or object

                # Split by pipe
                # Handle simplified splitting (assume no escaped pipes for now based on grep)
                items = [item.strip() for item in content.split('|')]

                new_items = []
                for item in items:
                    if ',' in item:
                        # Quote if comma present
                        # Escape existing quotes
                        escaped = item.replace('"', '\\"')
                        new_items.append(f'"{escaped}"')
                    else:
                        new_items.append(item)

                new_content = ",".join(new_items)
                new_lines.append(f'{indent}{key}[{count}]: {new_content}\n')
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(filepath, 'w') as f:
        f.writelines(new_lines)

def walk_dir(root):
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.toon'):
                process_file(os.path.join(dirpath, fname))

if __name__ == '__main__':
    walk_dir('ai-docs')
