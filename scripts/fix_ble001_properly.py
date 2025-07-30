#!/usr/bin/env python3
"""Fix BLE001 errors by replacing generic Exception with specific exceptions."""

import re
from pathlib import Path

# Map of common patterns to specific exceptions
EXCEPTION_MAPPING = {
    # File/IO operations
    "open": ["OSError", "IOError"],
    "read": ["OSError", "IOError"],
    "write": ["OSError", "IOError"],
    "path": ["OSError", "FileNotFoundError"],
    "file": ["OSError", "FileNotFoundError"],
    "mkdir": ["OSError"],
    "exists": ["OSError"],
    # JSON operations
    "json.load": ["json.JSONDecodeError", "ValueError"],
    "json.dump": ["ValueError", "TypeError"],
    # Import operations
    "import": ["ImportError", "ModuleNotFoundError"],
    "__import__": ["ImportError"],
    "importlib": ["ImportError"],
    # Subprocess operations
    "subprocess": ["subprocess.SubprocessError", "OSError"],
    "run": ["subprocess.SubprocessError", "OSError"],
    "popen": ["OSError"],
    # Network operations
    "requests": ["requests.RequestException"],
    "urlopen": ["OSError", "ValueError"],
    "connect": ["ConnectionError", "OSError"],
    # Type conversions
    "int(": ["ValueError", "TypeError"],
    "float(": ["ValueError", "TypeError"],
    "str(": ["TypeError"],
    # Attribute access
    "getattr": ["AttributeError"],
    "setattr": ["AttributeError"],
    "hasattr": ["AttributeError"],
    # Dictionary/List operations
    "[": ["KeyError", "IndexError"],
    "get(": ["KeyError", "AttributeError"],
    "pop(": ["KeyError", "IndexError"],
    # Parsing
    "parse": ["ValueError", "SyntaxError"],
    "compile": ["SyntaxError"],
    "ast.": ["SyntaxError", "ValueError"],
}


def get_context_window(lines: list[str], line_idx: int, window: int = 10) -> str:
    """Get context around a line."""
    start = max(0, line_idx - window)
    end = min(len(lines), line_idx + window)
    return "\n".join(lines[start:end])


def suggest_exceptions(context: str) -> list[str]:
    """Suggest specific exceptions based on context."""
    suggestions = set()
    context_lower = context.lower()

    # Check each pattern
    for pattern, exceptions in EXCEPTION_MAPPING.items():
        if pattern.lower() in context_lower:
            suggestions.update(exceptions)

    # If no specific match, use common exceptions
    if not suggestions:
        if "file" in context_lower or "path" in context_lower:
            suggestions.update(["OSError"])
        elif "parse" in context_lower:
            suggestions.update(["ValueError"])
        elif "type" in context_lower:
            suggestions.update(["TypeError", "ValueError"])
        else:
            suggestions.update(["RuntimeError", "ValueError"])

    return sorted(list(suggestions))[:3]  # Limit to 3 exceptions


def fix_file(file_path: Path) -> bool:
    """Fix BLE001 errors in a file."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            lines = f.readlines()

        modified = False
        i = 0

        while i < len(lines):
            line = lines[i].rstrip()

            # Check for 'except Exception:' or 'except Exception as e:'
            if re.match(r"^\s*except\s+Exception\s*:", line):
                indent = len(line) - len(line.lstrip())
                context = get_context_window(lines, i)
                exceptions = suggest_exceptions(context)

                if len(exceptions) == 1:
                    new_line = " " * indent + f"except {exceptions[0]}:\n"
                else:
                    new_line = " " * indent + f"except ({', '.join(exceptions)}):\n"

                lines[i] = new_line
                modified = True

            elif re.match(r"^\s*except\s+Exception\s+as\s+(\w+)\s*:", line):
                match = re.match(r"^(\s*)except\s+Exception\s+as\s+(\w+)\s*:", line)
                if match:
                    indent = len(match.group(1))
                    var_name = match.group(2)
                    context = get_context_window(lines, i)
                    exceptions = suggest_exceptions(context)

                    if len(exceptions) == 1:
                        new_line = (
                            " " * indent + f"except {exceptions[0]} as {var_name}:\n"
                        )
                    else:
                        new_line = (
                            " " * indent
                            + f"except ({', '.join(exceptions)}) as {var_name}:\n"
                        )

                    lines[i] = new_line
                    modified = True

            i += 1

        if modified:
            # Check if we need to add imports
            content = "".join(lines)
            imports_needed = set()

            if "json.JSONDecodeError" in content:
                # Check if json is imported
                if not any("import json" in line for line in lines):
                    imports_needed.add("import json")

            if "subprocess.SubprocessError" in content:
                if not any("import subprocess" in line for line in lines):
                    imports_needed.add("import subprocess")

            if "requests.RequestException" in content:
                if not any("import requests" in line for line in lines):
                    imports_needed.add("import requests")

            # Add imports after other imports
            if imports_needed:
                import_idx = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith(
                        ("import ", "from "),
                    ) and not line.strip().startswith("from __future__"):
                        import_idx = i + 1
                    elif (
                        line.strip()
                        and not line.strip().startswith("#")
                        and import_idx > 0
                    ):
                        break

                for imp in sorted(imports_needed):
                    lines.insert(import_idx, imp + "\n")
                    import_idx += 1

            with Path(file_path).open("w", encoding="utf-8") as f:
                f.writelines(lines)
            return True

    except (OSError, FileNotFoundError, ImportError) as e:
        print(f"Error processing {file_path}: {e}")

    return False


def main():
    """Main function."""
    # Get all Python files
    python_files = []
    for pattern in ["**/*.py"]:
        python_files.extend(Path().glob(pattern))

    # Exclude certain directories
    exclude_dirs = {
        ".git",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        ".claude",
        "grammars",
        "archive",
        "worktrees",
        "flask",
        "rust",
        "click",
        "gin",
        "guava",
        "googletest",
        "lodash",
        "ruby",
        "serde",
    }

    python_files = [
        f for f in python_files if not any(exc in f.parts for exc in exclude_dirs)
    ]

    fixed_count = 0
    for file_path in python_files:
        if fix_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
