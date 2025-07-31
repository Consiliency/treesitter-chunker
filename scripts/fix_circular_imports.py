#!/usr/bin/env python3
"""Fix circular imports in language files."""

from pathlib import Path
import re


def fix_circular_import(file_path: Path) -> bool:
    """Remove circular import from language file."""
    try:
        with file_path.open('r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern to find and remove the problematic import
        # This matches lines like "from . import language_config_registry"
        pattern = r'^from \. import language_config_registry\s*$'
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # Also remove any standalone usage of language_config_registry
        # at the module level (not inside functions/classes)
        pattern2 = r'^language_config_registry\.[^\n]+$'
        content = re.sub(pattern2, '', content, flags=re.MULTILINE)
        
        # Clean up any double blank lines
        content = re.sub(r'\n\n\n+', '\n\n', content)
        
        if content != original_content:
            with file_path.open('w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix circular imports in all language files."""
    language_dir = Path("chunker/languages")
    
    # Files that have the circular import
    problem_files = [
        "clojure.py", "dart.py", "javascript.py", "scala.py", "sql.py",
        "svelte.py", "vue.py", "zig.py", "c.py", "dockerfile.py",
        "haskell.py", "matlab.py", "nasm.py", "ocaml.py", "python.py",
        "wasm.py", "elixir.py", "julia.py", "r.py"
    ]
    
    fixed_count = 0
    for filename in problem_files:
        file_path = language_dir / filename
        if file_path.exists():
            if fix_circular_import(file_path):
                fixed_count += 1
                print(f"Fixed {file_path}")
    
    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()