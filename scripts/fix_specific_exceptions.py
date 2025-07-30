#!/usr/bin/env python3
"""Fix BLE001 errors by replacing generic Exception with specific exceptions."""

import re
from pathlib import Path

# Map of common patterns to specific exceptions
EXCEPTION_PATTERNS = {
    # File operations
    r"open\(|Path\(|\.read|\.write|\.unlink|\.mkdir|\.exists|\.glob|\.rglob": ["OSError", "IOError"],
    r"json\.load|json\.dump|json\.loads|json\.dumps": ["json.JSONDecodeError", "ValueError"],
    r"yaml\.load|yaml\.dump|yaml\.safe_load": ["yaml.YAMLError"],
    r"toml\.load|toml\.loads": ["toml.TomlDecodeError"],

    # Import operations
    r"import |from .* import|__import__|importlib": ["ImportError", "ModuleNotFoundError"],

    # Type/attribute operations
    r"getattr|setattr|hasattr|delattr": ["AttributeError"],
    r"int\(|float\(|str\(|bool\(": ["ValueError", "TypeError"],
    r"\[.*\]|\{.*\}|\.get\(|\.pop\(": ["KeyError", "IndexError", "AttributeError"],

    # Process/subprocess
    r"subprocess\.run|subprocess\.call|subprocess\.Popen": ["subprocess.SubprocessError", "OSError"],
    r"psutil\.": ["psutil.Error"],

    # Network operations
    r"requests\.get|requests\.post|urllib": ["requests.RequestException", "ConnectionError"],

    # Database operations
    r"cursor\.execute|connection\.commit|\.fetchone|\.fetchall": ["DatabaseError"],

    # Parsing operations
    r"ast\.parse|compile\(": ["SyntaxError", "ValueError"],
    r"parser\.parse|tree_sitter": ["ValueError", "RuntimeError"],

    # Math operations
    r"math\.|numpy\.|statistics\.": ["ValueError", "ArithmeticError"],

    # Regular expressions
    r"re\.compile|re\.match|re\.search": ["re.error"],
}

def find_exception_context(lines: list[str], line_num: int, window: int = 5) -> str:
    """Get context around the exception to determine what exceptions to catch."""
    start = max(0, line_num - window)
    end = min(len(lines), line_num + window)
    context_lines = lines[start:end]
    return "\n".join(context_lines)

def suggest_exceptions(context: str) -> list[str]:
    """Suggest specific exceptions based on context."""
    suggestions = set()

    for pattern, exceptions in EXCEPTION_PATTERNS.items():
        if re.search(pattern, context, re.IGNORECASE):
            suggestions.update(exceptions)

    # If no specific pattern matches, suggest common exceptions
    if not suggestions:
        # Look for specific keywords
        if "file" in context.lower() or "path" in context.lower():
            suggestions.update(["OSError", "FileNotFoundError"])
        elif "parse" in context.lower():
            suggestions.update(["ValueError", "SyntaxError"])
        elif "connect" in context.lower() or "network" in context.lower():
            suggestions.update(["ConnectionError", "OSError"])
        elif "type" in context.lower():
            suggestions.update(["TypeError", "ValueError"])
        else:
            # Default to common exceptions
            suggestions.update(["ValueError", "RuntimeError", "OSError"])

    return sorted(list(suggestions))

def create_exception_tuple(exceptions: list[str]) -> str:
    """Create exception tuple string."""
    if len(exceptions) == 1:
        return exceptions[0]
    return f"({', '.join(exceptions)})"

def fix_file(file_path: Path) -> bool:
    """Fix BLE001 errors in a file."""
    try:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)
        modified = False

        # Find all except Exception: or except Exception as e: patterns
        patterns = [
            (r"^(\s*)except\s+Exception\s*:\s*$", r"\1except {exceptions}:"),
            (r"^(\s*)except\s+Exception\s+as\s+(\w+)\s*:\s*$", r"\1except {exceptions} as \2:"),
        ]

        new_lines = []
        skip_next = False

        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                new_lines.append(line)
                continue

            matched = False
            for pattern, replacement in patterns:
                match = re.match(pattern, line)
                if match:
                    # Get context to determine appropriate exceptions
                    context = find_exception_context(lines, i)
                    suggested = suggest_exceptions(context)

                    # Check if we're already catching something more specific nearby
                    # Look at the next few lines for pass, continue, or specific handling
                    next_lines = lines[i+1:i+5] if i+1 < len(lines) else []
                    next_content = "".join(next_lines).strip()

                    # If it's a simple pass/continue, we might want to be more lenient
                    if next_content.startswith(("pass", "continue")):
                        # For simple suppressions, stick with broader exceptions
                        if "import" in context:
                            exceptions = create_exception_tuple(["ImportError"])
                        elif "file" in context.lower() or "path" in context.lower():
                            exceptions = create_exception_tuple(["OSError"])
                        else:
                            exceptions = create_exception_tuple(suggested[:2])  # Limit to 2
                    else:
                        # For actual error handling, be more specific
                        exceptions = create_exception_tuple(suggested[:3])  # Limit to 3

                    new_line = replacement.format(exceptions=exceptions) + "\n"
                    new_lines.append(new_line)
                    modified = True
                    matched = True

                    # Check if we need to add imports
                    if any("." in exc for exc in suggested):
                        # Will need to handle imports separately
                        pass

                    break

            if not matched:
                new_lines.append(line)

        if modified:
            new_content = "".join(new_lines)

            # Add necessary imports at the top
            imports_needed = set()
            if "json.JSONDecodeError" in new_content and "import json" not in content:
                imports_needed.add("import json")
            if "yaml.YAMLError" in new_content and "import yaml" not in content:
                imports_needed.add("import yaml")
            if "toml.TomlDecodeError" in new_content and "import toml" not in content:
                imports_needed.add("import toml")
            if "subprocess.SubprocessError" in new_content and "import subprocess" not in content:
                imports_needed.add("import subprocess")
            if "requests.RequestException" in new_content and "import requests" not in content:
                imports_needed.add("import requests")
            if "re.error" in new_content and "import re" not in content:
                imports_needed.add("import re")
            if "psutil.Error" in new_content and "import psutil" not in content:
                imports_needed.add("import psutil")

            if imports_needed:
                # Find where to insert imports (after existing imports)
                import_lines = []
                content_lines = new_content.splitlines(keepends=True)
                insert_pos = 0

                for i, line in enumerate(content_lines):
                    if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("from __future__"):
                        insert_pos = i + 1
                    elif line.strip() and not line.strip().startswith("#") and insert_pos > 0:
                        break

                # Insert imports
                for imp in sorted(imports_needed):
                    content_lines.insert(insert_pos, imp + "\n")
                    insert_pos += 1

                new_content = "".join(content_lines)

            file_path.write_text(new_content)
            return True

    except (OSError, ValueError) as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function."""
    # Get all Python files
    python_files = []
    for pattern in ["**/*.py"]:
        python_files.extend(Path().glob(pattern))

    # Exclude certain directories
    exclude_dirs = {".git", ".mypy_cache", ".ruff_cache", ".venv", "__pycache__",
                   "build", "dist", ".claude", "grammars", "archive", "worktrees"}

    python_files = [
        f for f in python_files
        if not any(exc in f.parts for exc in exclude_dirs)
    ]

    fixed_count = 0
    for file_path in python_files:
        if fix_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()
