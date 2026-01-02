import os
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check for multiline indicator: key followed by colon, space, pipe, and newline
        match = re.match(r'^(\s*)([^:]+):\s*\|\s*$', line)
        if match:
            indent = match.group(1)
            key = match.group(2)

            # Start collecting block
            block_content = []
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Check indentation of next line
                # It must be deeper than the key's indentation OR be empty
                if not next_line.strip():
                    # Empty line, usually part of block or spacer.
                    # If it's a spacer, we might include it or stop?
                    # YAML usually includes empty lines in blocks.
                    # But TOON might be strict.
                    # For safety, if next line is empty, treat as part of block but check line AFTER.
                    # Actually, simplistic approach: if next line has content and indent <= key indent, stop.
                    if i + 1 < len(lines):
                         next_next_line = lines[i+1]
                         block_match = re.match(r'^(\s*)', next_next_line)
                         if block_match and len(block_match.group(1)) <= len(indent) and next_next_line.strip():
                             break
                    block_content.append("")
                    i += 1
                    continue

                next_indent_match = re.match(r'^(\s*)', next_line)
                next_indent = next_indent_match.group(1) if next_indent_match else ""

                if len(next_indent) > len(indent):
                    # It's inside the block
                    # Strip the base indentation (indent + 2 spaces usually, or just whatever it is)
                    # But we want to preserve relative indentation?
                    # For now just strip leading whitespace and join with \n is safest for prose.
                    # But for 'code', indentation matters.
                    # Let's preserve relative indentation if possible.

                    # Calculate relative indent
                    # We assume the first line defines the block indent
                    content = next_line.rstrip('\n')
                    # We can't actally know "block indent" until we fail.
                    # But effectively we just need to double quote it.
                    # Let's simple strip the key's indent level + 2 spaces?
                    # Or just strip leading whitespace completely?
                    # For `code: |` blocks, indentation is critical.
                    # Example:
                    # code: |
                    #   function() {
                    #     return true;
                    #   }
                    # Should become: "function() {\n  return true;\n}"

                    # Heuristic: strip len(indent) + 2 characters from start?
                    # The standard indent is 2 spaces in this project.
                    base_block_indent = len(indent) + 2
                    if len(next_indent) >= base_block_indent:
                        stripped_content = content[base_block_indent:]
                    else:
                        stripped_content = content.strip() # Fallback

                    block_content.append(stripped_content)
                    i += 1
                else:
                    # End of block
                    break

            # Create replacement line
            # Escape quotes and backslashes
            final_str = "\\n".join(block_content)
            final_str = final_str.replace('\\', '\\\\').replace('"', '\\"')
            new_lines.append(f'{indent}{key}: "{final_str}"\n')
        else:
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
