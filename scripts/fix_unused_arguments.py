#!/usr/bin/env python3
"""Fix ARG001, ARG002, ARG005 errors by prefixing unused arguments with underscore."""

import ast
import re
from pathlib import Path


class UnusedArgumentFixer(ast.NodeVisitor):
    """AST visitor to fix unused arguments."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.fixes = []  # List of (line, col_offset, old_name, new_name)
        self.current_function = None
        self.used_names = set()

    def visit_FunctionDef(self, node):
        """Visit function definition."""
        # Save previous state
        prev_function = self.current_function
        prev_used_names = self.used_names

        self.current_function = node
        self.used_names = set()

        # First pass: collect all used names in function body
        for stmt in node.body:
            self._collect_used_names(stmt)

        # Check arguments
        self._check_arguments(node)

        # Visit nested functions
        self.generic_visit(node)

        # Restore state
        self.current_function = prev_function
        self.used_names = prev_used_names

    visit_AsyncFunctionDef = visit_FunctionDef

    def _collect_used_names(self, node):
        """Collect all names used in the node."""
        if isinstance(node, ast.Name):
            self.used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # For self.x, add 'self' to used names
            if isinstance(node.value, ast.Name):
                self.used_names.add(node.value.id)

        # Recursively check all child nodes
        for child in ast.iter_child_nodes(node):
            self._collect_used_names(child)

    def _check_arguments(self, func_node):
        """Check function arguments for unused ones."""
        # Skip certain function patterns
        if self._should_skip_function(func_node):
            return

        # Check regular args
        for arg in func_node.args.args:
            if arg.arg not in self.used_names and not arg.arg.startswith("_"):
                # Special cases to skip
                if arg.arg in {"self", "cls"} and func_node.args.args.index(arg) == 0:
                    continue
                if self._is_protocol_method(func_node):
                    continue
                if self._is_override_method(func_node):
                    continue

                self.fixes.append((arg.lineno, arg.col_offset, arg.arg, f"_{arg.arg}"))

        # Check kwonlyargs
        for arg in func_node.args.kwonlyargs:
            if arg.arg not in self.used_names and not arg.arg.startswith("_"):
                self.fixes.append((arg.lineno, arg.col_offset, arg.arg, f"_{arg.arg}"))

    def _should_skip_function(self, node):
        """Check if function should be skipped."""
        # Skip test functions - they often have fixtures as unused args
        if node.name.startswith("test_"):
            return True

        # Skip special methods that might be part of protocols
        special_methods = {
            "__init__",
            "__new__",
            "__del__",
            "__repr__",
            "__str__",
            "__bytes__",
            "__format__",
            "__lt__",
            "__le__",
            "__eq__",
            "__ne__",
            "__gt__",
            "__ge__",
            "__hash__",
            "__bool__",
            "__getattr__",
            "__getattribute__",
            "__setattr__",
            "__delattr__",
            "__dir__",
            "__get__",
            "__set__",
            "__delete__",
            "__set_name__",
            "__slots__",
            "__init_subclass__",
            "__prepare__",
            "__instancecheck__",
            "__subclasscheck__",
            "__call__",
            "__len__",
            "__length_hint__",
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__missing__",
            "__iter__",
            "__reversed__",
            "__contains__",
            "__add__",
            "__sub__",
            "__mul__",
            "__matmul__",
            "__truediv__",
            "__floordiv__",
            "__mod__",
            "__divmod__",
            "__pow__",
            "__lshift__",
            "__rshift__",
            "__and__",
            "__xor__",
            "__or__",
            "__radd__",
            "__rsub__",
            "__rmul__",
            "__rmatmul__",
            "__rtruediv__",
            "__rfloordiv__",
            "__rmod__",
            "__rdivmod__",
            "__rpow__",
            "__rlshift__",
            "__rrshift__",
            "__rand__",
            "__rxor__",
            "__ror__",
            "__iadd__",
            "__isub__",
            "__imul__",
            "__imatmul__",
            "__itruediv__",
            "__ifloordiv__",
            "__imod__",
            "__ipow__",
            "__ilshift__",
            "__irshift__",
            "__iand__",
            "__ixor__",
            "__ior__",
            "__neg__",
            "__pos__",
            "__abs__",
            "__invert__",
            "__complex__",
            "__int__",
            "__float__",
            "__index__",
            "__round__",
            "__trunc__",
            "__floor__",
            "__ceil__",
            "__enter__",
            "__exit__",
            "__await__",
            "__aiter__",
            "__anext__",
            "__aenter__",
            "__aexit__",
        }

        if node.name in special_methods:
            return True

        # Skip decorated functions that might be callbacks
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id in {
                    "property",
                    "staticmethod",
                    "classmethod",
                    "abstractmethod",
                    "click.command",
                    "click.option",
                }:
                    return True
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr in {
                    "setter",
                    "deleter",
                    "command",
                    "option",
                    "argument",
                }:
                    return True

        return False

    def _is_protocol_method(self, node):
        """Check if method is part of a protocol/interface."""
        # Look for common protocol decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
                return True
            if (
                isinstance(decorator, ast.Attribute)
                and decorator.attr == "abstractmethod"
            ):
                return True

        # Check if method raises NotImplementedError
        for stmt in node.body:
            if isinstance(stmt, ast.Raise):
                if isinstance(stmt.exc, ast.Call):
                    if (
                        isinstance(stmt.exc.func, ast.Name)
                        and stmt.exc.func.id == "NotImplementedError"
                    ):
                        return True

        return False

    def _is_override_method(self, node):
        """Check if method is likely overriding a parent method."""
        # Simple heuristic: if it has common override patterns
        override_patterns = {"visit_", "process_", "handle_", "on_", "do_"}

        for pattern in override_patterns:
            if node.name.startswith(pattern):
                return True

        return False


def fix_file(file_path: Path) -> bool:
    """Fix unused arguments in a file."""
    try:
        with Path(file_path).open(encoding="utf-8") as f:
            source = f.read()
            lines = source.splitlines(keepends=True)

        # Parse AST
        try:
            tree = ast.parse(source)
        except SyntaxError:
            print(f"Syntax error in {file_path}, skipping")
            return False

        # Find unused arguments
        fixer = UnusedArgumentFixer(lines)
        fixer.visit(tree)

        if not fixer.fixes:
            return False

        # Apply fixes from bottom to top to avoid offset issues
        fixer.fixes.sort(key=lambda x: (x[0], x[1]), reverse=True)

        for line_no, col_offset, old_name, new_name in fixer.fixes:
            # Find the line
            if line_no <= len(lines):
                line = lines[line_no - 1]

                # Use regex to replace the argument name
                # Be careful to match whole words only
                pattern = r"\b" + re.escape(old_name) + r"\b"

                # Check if this replacement is safe
                if re.search(pattern, line):
                    # Count occurrences to ensure we're replacing the right one
                    matches = list(re.finditer(pattern, line))

                    # Try to find the match closest to col_offset
                    best_match = None
                    for match in matches:
                        if best_match is None or abs(match.start() - col_offset) < abs(
                            best_match.start() - col_offset,
                        ):
                            best_match = match

                    if best_match:
                        # Replace this specific occurrence
                        new_line = (
                            line[: best_match.start()]
                            + new_name
                            + line[best_match.end() :]
                        )
                        lines[line_no - 1] = new_line

        # Write back
        new_content = "".join(lines)
        with Path(file_path).open("w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Fixed {file_path}")
        return True

    except Exception as e:
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
        # Skip test files for now - they often have legitimate unused fixtures
        if "test_" in file_path.name or "tests" in file_path.parts:
            continue

        if fix_file(file_path):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
