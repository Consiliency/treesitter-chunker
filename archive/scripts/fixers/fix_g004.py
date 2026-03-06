#!/usr/bin/env python3
"""Fix G004 errors - logging with f-strings instead of % formatting."""

import re
from pathlib import Path


def convert_fstring_to_percent(fstring_content):
    """Convert f-string content to % formatting."""
    # Pattern to match f-string expressions like {var} or {expr}
    expr_pattern = re.compile(r"\{([^}]+)\}")

    format_str = fstring_content
    args = []

    # Replace each expression with %s and collect the expressions
    def replace_expr(match):
        expr = match.group(1)
        args.append(expr)
        return "%s"

    format_str = expr_pattern.sub(replace_expr, format_str)

    return format_str, args


def fix_logging_fstrings(file_path: Path) -> bool:
    """Fix logging f-strings in a file."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            content = f.read()

        original = content

        # Pattern to match logging calls with f-strings
        # Matches: logger.method(f"...") or logging.method(f"...")
        patterns = [
            # Standard logging pattern
            re.compile(
                r'(\b(?:logger|logging|log|self\.logger|self\.log|cls\.logger)\.(?:debug|info|warning|error|critical|exception))\s*\(\s*f(["\'])(.+?)\2\s*\)',
                re.DOTALL,
            ),
            # With additional arguments
            re.compile(
                r'(\b(?:logger|logging|log|self\.logger|self\.log|cls\.logger)\.(?:debug|info|warning|error|critical|exception))\s*\(\s*f(["\'])(.+?)\2\s*,([^)]+)\)',
                re.DOTALL,
            ),
        ]

        # Process standard logging pattern
        def replace_simple_fstring(match):
            method = match.group(1)
            quote = match.group(2)
            fstring_content = match.group(3)

            # Convert f-string to % formatting
            format_str, args = convert_fstring_to_percent(fstring_content)

            if args:
                args_str = ", ".join(args)
                return f"{method}({quote}{format_str}{quote}, {args_str})"
            # No interpolation, just remove the f prefix
            return f"{method}({quote}{fstring_content}{quote})"

        # Process pattern with additional arguments
        def replace_fstring_with_args(match):
            method = match.group(1)
            quote = match.group(2)
            fstring_content = match.group(3)
            extra_args = match.group(4)

            # Convert f-string to % formatting
            format_str, args = convert_fstring_to_percent(fstring_content)

            if args:
                args_str = ", ".join(args)
                return f"{method}({quote}{format_str}{quote}, {args_str},{extra_args})"
            # No interpolation, just remove the f prefix
            return f"{method}({quote}{fstring_content}{quote},{extra_args})"

        # Apply replacements
        modified = content
        modified = patterns[0].sub(replace_simple_fstring, modified)
        modified = patterns[1].sub(replace_fstring_with_args, modified)

        # Also handle multiline f-strings in logging
        multiline_pattern = re.compile(
            r'(\b(?:logger|logging|log|self\.logger|self\.log|cls\.logger)\.(?:debug|info|warning|error|critical|exception))\s*\(\s*\n?\s*f"""(.+?)"""\s*(?:,([^)]+))?\)',
            re.DOTALL,
        )

        def replace_multiline_fstring(match):
            method = match.group(1)
            fstring_content = match.group(2)
            extra_args = match.group(3)

            # Convert f-string to % formatting
            format_str, args = convert_fstring_to_percent(fstring_content)

            if args:
                args_str = ", ".join(args)
                if extra_args:
                    return f'{method}("""{format_str}""", {args_str}, {extra_args})'
                return f'{method}("""{format_str}""", {args_str})'
            if extra_args:
                return f'{method}("""{fstring_content}""", {extra_args})'
            return f'{method}("""{fstring_content}""")'

        modified = multiline_pattern.sub(replace_multiline_fstring, modified)

        if modified != original:
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(modified)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

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
        if fix_logging_fstrings(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
