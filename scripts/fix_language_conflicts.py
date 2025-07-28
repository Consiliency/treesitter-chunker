#!/usr/bin/env python3
"""Fix language plugin conflicts by taking the GoConfig/JavaConfig/RubyConfig class versions."""

import re
from pathlib import Path


def fix_language_plugin(file_path):
    """Fix a language plugin file by keeping the class-based config."""
    content = file_path.read_text()

    # Check if there's a conflict
    if "<<<<<<< HEAD" not in content:
        print(f"No conflicts in {file_path}")
        return

    # Extract the class name (GoConfig, JavaConfig, RubyConfig)
    language = file_path.stem.replace("_plugin", "").title()
    config_class = f"{language}Config"

    # Find the class definition section from main branch
    # This is between the first "class XXXConfig" and "language_config_registry.register"
    class_pattern = rf"class {config_class}\(LanguageConfig\):.*?language_config_registry\.register\({language.lower()}_config\)"

    # Extract content before conflict
    before_conflict = content.split("<<<<<<< HEAD")[0]

    # Find the class definition in the conflict (it's in the main branch section)
    if "=======" in content and "class " + config_class in content:
        # Split by conflict markers
        parts = content.split("=======")
        if len(parts) >= 2:
            # The main branch content is after the first =======
            main_content = parts[1]

            # Find the class definition
            class_match = re.search(
                rf"(class {config_class}\(LanguageConfig\):.*?language_config_registry\.register\({language.lower()}_config\))",
                main_content,
                re.DOTALL,
            )

            if class_match:
                class_def = class_match.group(1)
                # Clean up any remaining conflict markers
                class_def = re.sub(r"<<<<<<< [^\n]+\n", "", class_def)
                class_def = re.sub(r">>>>>>> [^\n]+\n", "", class_def)
                class_def = re.sub(r"=======\n", "", class_def)

                # Combine with the content before conflict
                new_content = before_conflict.rstrip() + "\n\n" + class_def + "\n"

                file_path.write_text(new_content)
                print(f"Fixed {file_path}")
                return

    print(f"Could not automatically fix {file_path} - manual intervention needed")


# Fix the language plugin files
plugin_files = [
    Path(
        "/home/jenner/code/treesitter-chunker-worktrees/metadata-extraction/chunker/languages/go_plugin.py",
    ),
    Path(
        "/home/jenner/code/treesitter-chunker-worktrees/metadata-extraction/chunker/languages/java_plugin.py",
    ),
    Path(
        "/home/jenner/code/treesitter-chunker-worktrees/metadata-extraction/chunker/languages/ruby_plugin.py",
    ),
]

for plugin_file in plugin_files:
    if plugin_file.exists():
        fix_language_plugin(plugin_file)
