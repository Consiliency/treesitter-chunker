#!/usr/bin/env python3
"""Script to fix G004 (logging f-string) errors."""

import re
from pathlib import Path


def fix_logging_fstrings(file_path):
    """Fix G004 errors in a single file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content

        # Pattern to match logger calls with f-strings
        # Matches logger.info(f"..."), logger.debug(f"..."), etc.
        pattern = re.compile(
            r'(logger\.(debug|info|warning|error|critical))\(f["\']([^"\']*)\{([^}]+)\}([^"\']*)["\']([^)]*)\)',
            re.MULTILINE,
        )

        def replace_fstring(match):
            method = match.group(1)  # logger.info
            template = match.group(3) + "%s" + match.group(5)  # Template with %s
            var = match.group(4)  # Variable
            extra = match.group(6)  # Any extra args

            # Handle multiple variables in f-string
            full_match = match.group(0)
            if full_match.count("{") > 1:
                # Complex f-string, skip for manual review
                return full_match

            if extra:
                return f'{method}("{template}", {var}{extra})'
            return f'{method}("{template}", {var})'

        # First pass - simple f-strings
        content = pattern.sub(replace_fstring, content)

        # Pattern for f-strings with multiple variables
        complex_pattern = re.compile(
            r'(logger\.(debug|info|warning|error|critical))\(f["\']([^"\']+)["\']([^)]*)\)',
        )

        def extract_vars_from_fstring(fstring_content):
            """Extract variables from f-string content."""
            variables = []
            parts = []
            current_part = ""
            in_brace = False
            brace_content = ""

            for char in fstring_content:
                if char == "{" and not in_brace:
                    in_brace = True
                    parts.append(current_part)
                    current_part = ""
                elif char == "}" and in_brace:
                    in_brace = False
                    variables.append(brace_content.strip())
                    parts.append("%s")
                    brace_content = ""
                elif in_brace:
                    brace_content += char
                else:
                    current_part += char

            if current_part:
                parts.append(current_part)

            return "".join(parts), variables

        def replace_complex_fstring(match):
            method = match.group(1)
            fstring_content = match.group(3)
            extra = match.group(4)

            # Skip if not an f-string
            if not match.group(0).startswith(method + "(f"):
                return match.group(0)

            template, variables = extract_vars_from_fstring(fstring_content)

            if not variables:
                return match.group(0)

            variables_str = ", ".join(vars)

            if extra:
                return f'{method}("{template}", {vars_str}{extra})'
            return f'{method}("{template}", {vars_str})'

        # Second pass - complex f-strings
        lines = content.split("\n")
        new_lines = []

        for line in lines:
            if ("logger." in line and '(f"' in line) or "(f'" in line:
                # Process line with regex
                new_line = complex_pattern.sub(replace_complex_fstring, line)
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        content = "\n".join(new_lines)

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except (OSError, FileNotFoundError, IndexError) as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix G004 errors in the codebase."""

    # Get all Python files
    files_to_check = []
    for pattern in ["chunker/**/*.py", "tests/**/*.py", "cli/**/*.py", "benchmarks/**/*.py", "examples/**/*.py", "scripts/**/*.py"]:
        files_to_check.extend(Path().glob(pattern))

    fixed = 0
    total = 0

    for file_path in files_to_check:
        if "fix_logging_fstrings.py" in str(file_path):
            continue

        # Check if file has logging f-strings
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                if "logger." in content and ('(f"' in content or "(f'" in content):
                    total += 1
                    if fix_logging_fstrings(file_path):
                        print(f"Fixed: {file_path}")
                        fixed += 1
        except (FileNotFoundError, OSError) as e:
            print(f"Error checking {file_path}: {e}")

    print(f"\nFixed {fixed}/{total} files with logging f-strings")


if __name__ == "__main__":
    main()
