"""Fix G004 - logging statements using f-strings.

Converts f-strings in logging statements to % formatting with lazy evaluation.
"""
import ast
import re
from pathlib import Path
from typing import Any


class LoggingFStringFixer(ast.NodeTransformer):
    """AST transformer to fix f-strings in logging statements."""

    def __init__(self):
        self.changes_made = []
        self.logging_modules = {"logger", "logging", "log", "self.logger",
            "self.log"}

    def visit_Call(self, node):
        """Visit function calls to find logging statements."""
        if self._is_logging_call(node):
            new_args = []
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):
                    new_arg = self._convert_fstring_to_percent(arg)
                    if new_arg:
                        new_args.append(new_arg)
                        self.changes_made.append(
                            f"Converted f-string to % formatting in {self._get_call_name(node)} call",
                            )
                    else:
                        new_args.append(arg)
                else:
                    new_args.append(arg)
            node.args = new_args
        return self.generic_visit(node)

    def _is_logging_call(self, node) -> bool:
        """Check if a call is a logging statement."""
        if isinstance(node.func, ast.Attribute):
            if (hasattr(node.func.value, "id",
                ) and node.func.value.id in self.logging_modules) or (isinstance(node.func.value, ast.Attribute) and (isinstance
                (node.func.value.value, ast.Name) and node.func.value.value
                .id == "self" and node.func.value.attr in ("logger", "log"))):
                return node.func.attr in ("debug", "info", "warning",
                    "error", "critical", "log")
        elif isinstance(node.func, ast.Name):
            return node.func.id in ("debug", "info", "warning", "error",
                "critical")
        return False

    def _get_call_name(self, node) -> str:
        """Get the name of the logging call."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
        return "logging"

    def _convert_fstring_to_percent(self, fstring_node) -> ast.AST:
        """Convert an f-string to % formatting."""
        if not isinstance(fstring_node, ast.JoinedStr):
            return None
        format_parts = []
        format_args = []
        for value in fstring_node.values:
            if isinstance(value, ast.Constant):
                format_parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                if value.conversion == -1 and value.format_spec is None:
                    format_parts.append("%s")
                else:
                    format_parts.append("%s")
                format_args.append(value.value)
        format_string = "".join(format_parts)
        if not format_args:
            return ast.Constant(value=format_string)
        if len(format_args) == 1:
            return ast.BinOp(left=ast.Constant(value=format_string), op=ast
                .Mod(), right=format_args[0])
        return ast.BinOp(left=ast.Constant(value=format_string), op=ast
            .Mod(), right=ast.Tuple(elts=format_args, ctx=ast.Load()))


def fix_file(file_path: Path) -> list[str]:
    """Fix f-strings in logging statements in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []
    fixer = LoggingFStringFixer()
    new_tree = fixer.visit(tree)
    if fixer.changes_made:
        try:
            import astor
            new_code = astor.to_source(new_tree)
        except ImportError:
            new_code = ast.unparse(new_tree)
        file_path.write_text(new_code, encoding="utf-8")
        return fixer.changes_made
    return []


def fix_file_with_regex(file_path: Path) -> list[str]:
    """Alternative approach using regex for more complex cases."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []
    changes = []
    lines = content.splitlines(keepends=True)
    modified = False
    logging_pattern = re.compile(
        '(\\s*)((?:self\\.)?(?:logger|log|logging)\\.(?:debug|info|warning|error|critical)|(?:debug|info|warning|error|critical))\\s*\\(\\s*f["\\\']',
        )
    for i, line in enumerate(lines):
        match = logging_pattern.search(line)
        if match:
            start_pos = match.end() - 2
            quote_char = line[start_pos]
            end_pos = start_pos + 1
            while end_pos < len(line):
                if line[end_pos] == quote_char and line[end_pos - 1] != "\\":
                    break
                end_pos += 1
            if end_pos < len(line):
                fstring_content = line[start_pos + 1:end_pos]
                converted = convert_fstring_content(fstring_content)
                if converted:
                    new_line = line[:match.end() - 2] + quote_char + converted[
                        "format"] + quote_char + (", " + ", ".join(
                        converted["args"]) if converted["args"] else ""
                        ) + line[end_pos + 1:]
                    lines[i] = new_line
                    modified = True
                    changes.append(
                        f"Converted f-string in {match.group(2)} call")
    if modified:
        file_path.write_text("".join(lines), encoding="utf-8")
    return changes


def convert_fstring_content(content: str) -> dict[str, Any]:
    """Convert f-string content to % format."""
    expr_pattern = re.compile(r"\\{([^}]+)\\}")
    format_str = content
    args = []

    def replacer(match):
        expr = match.group(1)
        args.append(expr)
        return "%s"
    format_str = expr_pattern.sub(replacer, format_str)
    if args:
        return {"format": format_str, "args": args}
    return None


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    exclude_dirs = {".venv", "venv", "build", "dist", ".git", "ide",
        "node_modules", "grammars", "__pycache__", ".mypy_cache",
        ".ruff_cache", ".pytest_cache", "egg-info"}
    python_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                if "egg-info" not in str(file_path):
                    python_files.append(file_path)
    print(f"Found {len(python_files)} Python files to check")
    total_changes = []
    files_changed = 0
    for file_path in python_files:
        changes = fix_file(file_path)
        if not changes:
            changes = fix_file_with_regex(file_path)
        if changes:
            files_changed += 1
            total_changes.extend(changes)
            print(f"\n{file_path}:")
            for change in changes:
                print(f"  - {change}")
    print("\n\nSummary:")
    print(f"Files changed: {files_changed}")
    print(f"Total changes: {len(total_changes)}")


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, Path(Path(Path(__file__).resolve()).parent).parent)
    main()
