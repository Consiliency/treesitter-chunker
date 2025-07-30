#!/usr/bin/env python3
"""Fix all language plugins to use proper ChunkRule initialization."""

import re
from pathlib import Path


def fix_plugin_file(filepath):
    """Fix a single plugin file."""
    with Path(filepath).open(
        "r",
    ) as f:
        content = f.read()

    # Check if file has the problematic pattern
    if "ChunkRule(" not in content or "name=" not in content:
        return False

    # Fix ChunkRule instantiations with name parameter
    pattern = r'ChunkRule\s*\(\s*name\s*=\s*"[^"]+"\s*,\s*node_types\s*=\s*\[([^\]]+)\]\s*,\s*[^)]+\)'

    def replace_chunk_rule(match):
        # Extract the content and parse it
        full_match = match.group(0)

        # Extract node types
        node_types_match = re.search(r"node_types\s*=\s*\[([^\]]+)\]", full_match)
        if node_types_match:
            node_types = node_types_match.group(1)
            # Convert to set notation
            node_types_set = "{" + node_types + "}"
        else:
            return full_match

        # Extract name for metadata
        name_match = re.search(r'name\s*=\s*"([^"]+)"', full_match)
        name = name_match.group(1) if name_match else "chunk"

        # Extract other parameters
        min_lines = re.search(r"min_lines\s*=\s*(\d+)", full_match)
        max_lines = re.search(r"max_lines\s*=\s*(\d+)", full_match)
        re.search(r"include_context\s*=\s*(\w+)", full_match)

        # Build new ChunkRule
        new_rule = f'ChunkRule(\n            node_types={node_types_set},\n            include_children=True,\n            priority=5,\n            metadata={{"type": "{name}"'

        if min_lines:
            new_rule += f', "min_lines": {min_lines.group(1)}'
        if max_lines:
            new_rule += f', "max_lines": {max_lines.group(1)}'

        new_rule += "}\n        )"

        return new_rule

    # Apply the fix
    new_content = re.sub(
        pattern,
        replace_chunk_rule,
        content,
        flags=re.MULTILINE | re.DOTALL,
    )

    if new_content != content:
        with Path(filepath).open(
            "w",
        ) as f:
            f.write(new_content)
        return True

    return False


# Find all plugin files
plugin_dir = Path("chunker/languages")
plugin_files = list(plugin_dir.glob("*_plugin.py"))

print(f"Found {len(plugin_files)} plugin files")

for plugin_file in plugin_files:
    if fix_plugin_file(plugin_file):
        print(f"Fixed: {plugin_file}")
    else:
        print(f"Skipped: {plugin_file} (no changes needed)")
