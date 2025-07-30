#!/usr/bin/env python3
"""Fix PLC0415 errors by moving imports to top level."""

import ast
from pathlib import Path


class ImportFixer(ast.NodeVisitor):
    """AST visitor to find non-top-level imports."""

    def __init__(self, lines: list[str]):
        self.lines = lines
        self.non_top_imports = []  # List of (line, import_statement, context)
        self.in_function = False
        self.in_class = False
        self.function_stack = []

    def visit_FunctionDef(self, node):
        """Visit function definition."""
        self.function_stack.append(node.name)
        self.in_function = True

        # Check for imports in function body
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self._record_import(stmt, f"function {node.name}")

        self.generic_visit(node)
        self.function_stack.pop()
        if not self.function_stack:
            self.in_function = False

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        """Visit class definition."""
        old_in_class = self.in_class
        self.in_class = True

        # Check for imports in class body
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self._record_import(stmt, f"class {node.name}")

        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_If(self, node):
        """Visit if statement."""
        # Check for imports in if body
        for stmt in node.body + node.orelse:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                context = "conditional block"
                if self.function_stack:
                    context = f"{context} in {self.function_stack[-1]}"
                self._record_import(stmt, context)

        self.generic_visit(node)

    def visit_Try(self, node):
        """Visit try/except block."""
        # Check all parts of try/except
        for stmt in node.body + node.orelse + node.finalbody:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                context = "try block"
                if self.function_stack:
                    context = f"{context} in {self.function_stack[-1]}"
                self._record_import(stmt, context)

        # Check except handlers
        for handler in node.handlers:
            for stmt in handler.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    context = "except block"
                    if self.function_stack:
                        context = f"{context} in {self.function_stack[-1]}"
                    self._record_import(stmt, context)

        self.generic_visit(node)

    def _record_import(self, node, context):
        """Record a non-top-level import."""
        import_line = self.lines[node.lineno - 1].strip()
        self.non_top_imports.append((node.lineno, import_line, context, node))


def should_move_import(import_stmt: str, context: str) -> bool:
    """Determine if an import should be moved to top level."""
    # Don't move imports that are clearly conditional or lazy
    if any(
        phrase in context.lower() for phrase in ["except", "error", "optional", "lazy"]
    ):
        # Check if it's a common pattern that should stay
        if "traceback" in import_stmt and "except" in context:
            return False  # Keep traceback imports in except blocks
        if "typing" in import_stmt and "TYPE_CHECKING" in context:
            return False  # Keep TYPE_CHECKING imports
        if any(pkg in import_stmt for pkg in ["matplotlib", "graphviz", "PIL", "cv2"]):
            return False  # Keep optional visualization imports

    # Don't move test-specific imports in test functions
    if "test_" in context and any(
        pkg in import_stmt for pkg in ["pytest", "mock", "unittest"]
    ):
        return False

    # Move most other imports
    return True


def fix_file(file_path: Path) -> bool:
    """Fix import placement in a file."""
    try:
        with Path(file_path).Path("r").open(encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines(keepends=True)

        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return False

        # Find non-top-level imports
        fixer = ImportFixer(lines)
        fixer.visit(tree)

        if not fixer.non_top_imports:
            return False

        # Determine which imports to move
        imports_to_move = []
        lines_to_remove = set()

        for line_no, import_stmt, context, node in fixer.non_top_imports:
            if should_move_import(import_stmt, context):
                imports_to_move.append(import_stmt)
                lines_to_remove.add(line_no - 1)  # 0-indexed

        if not imports_to_move:
            return False

        # Find where to insert imports
        insert_line = 0
        has_future_imports = False
        has_regular_imports = False

        for i, line in enumerate(lines):
            if line.strip().startswith('"""') and i == 0:
                # Skip module docstring
                in_docstring = True
                for j in range(i + 1, len(lines)):
                    if '"""' in lines[j]:
                        insert_line = j + 1
                        break
            elif line.strip().startswith("from __future__"):
                has_future_imports = True
                insert_line = i + 1
            elif (
                line.strip().startswith(("import ", "from "))
                and not has_regular_imports
            ):
                has_regular_imports = True
                if not has_future_imports:
                    insert_line = i
            elif (
                line.strip()
                and not line.strip().startswith("#")
                and has_regular_imports
            ):
                break

        # Build new content
        new_lines = []

        # Add imports at the right position
        for i, line in enumerate(lines):
            if i == insert_line and imports_to_move:
                # Add a blank line if needed
                if (
                    i > 0
                    and lines[i - 1].strip()
                    and not lines[i - 1].strip().startswith(("import", "from"))
                ):
                    new_lines.append("\n")

                # Add the moved imports
                for imp in sorted(set(imports_to_move)):
                    new_lines.append(imp + "\n")

                # Add a blank line after imports if needed
                if line.strip() and not line.strip().startswith(("import", "from")):
                    new_lines.append("\n")

            # Skip lines that we're moving
            if i not in lines_to_remove:
                new_lines.append(line)

        # Write back
        new_content = "".join(new_lines)
        with Path(file_path).Path("w").open(encoding="utf-8") as f:
            f.write(new_content)

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
        if fix_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
