import os

def process_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []

    # We want to remove blank lines IF the next line starts with "- " (list item)
    # Iterate through lines
    # If current is blank, peek ahead.

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            # Blank line
            # Peek ahead until non-blank
            j = i + 1
            has_list_next = False
            while j < len(lines):
                if lines[j].strip():
                   # Found content
                   if lines[j].strip().startswith('- '):
                       has_list_next = True
                   break
                j += 1

            if has_list_next:
                # This blank line (and subsequent blank lines) precede a list item.
                # Remove them?
                # Usually removing one blank line is enough to adhere to "compact list".
                # But let's just skip this line.
                i += 1
                continue

        new_lines.append(line)
        i += 1

    with open(filepath, 'w') as f:
        f.writelines(new_lines)

def walk_dir(root):
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.toon'):
                process_file(os.path.join(dirpath, fname))

if __name__ == '__main__':
    walk_dir('ai-docs')
