"""Fix PERF401 - Convert manual list comprehensions to proper list comprehensions using AST."""
import ast
import os
from pathlib import Path


class ListComprehensionTransformer(ast.NodeTransformer):
    """Transform manual list building patterns to list comprehensions."""

    def __init__(self):
        self.changes_made = False
        self.in_function_or_method = False

    def visit_FunctionDef(self, node):
        """Track when we're inside a function."""
        old_in_function = self.in_function_or_method
        self.in_function_or_method = True
        self.generic_visit(node)
        self.in_function_or_method = old_in_function
        return node

    def visit_AsyncFunctionDef(self, node):
        """Track when we're inside an async function."""
        return self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        """Visit class definitions."""
        self.generic_visit(node)
        return node

    def visit_For(self, node):
        """Look for patterns that can be converted to list comprehensions."""
        self.generic_visit(node)
        if len(node.body) == 1 and isinstance(node.body[0], ast.Expr,
            ) and isinstance(node.body[0].value, ast.Call) and isinstance(node
            .body[0].value.func, ast.Attribute) and node.body[0
            ].value.func.attr == "append":
            pass
        return node

    def visit_Module(self, node):
        """Visit module and look for list comprehension patterns."""
        new_body = []
        i = 0
        while i < len(node.body):
            current = node.body[i]
            if i + 1 < len(node.body) and isinstance(current, ast.Assign,
                ) and len(current.targets) == 1 and isinstance(current.
                targets[0], ast.Name) and isinstance(current.value, ast.List,
                ) and len(current.value.elts) == 0:
                list_var = current.targets[0].id
                next_stmt = node.body[i + 1]
                if isinstance(next_stmt, ast.For,
                    ) and self._is_simple_append_loop(next_stmt, list_var):
                    list_comp = self._create_list_comprehension(next_stmt,
                        list_var)
                    if list_comp:
                        new_assign = ast.Assign(targets=[ast.Name(id=list_var, ctx=ast.Store())], value=list_comp)
                        ast.fix_missing_locations(new_assign)
                        new_body.append(new_assign)
                        self.changes_made = True
                        i += 2
                        continue
            new_body.append(self.visit(current))
            i += 1
        node.body = new_body
        return node

    @staticmethod
    def _is_simple_append_loop(for_node, list_var):
        """Check if a for loop is a simple append pattern."""
        if len(for_node.body) != 1:
            return False
        stmt = for_node.body[0]
        if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and
            isinstance(stmt.value.func, ast.Attribute) and isinstance(stmt.
            value.func.value, ast.Name) and stmt.value.func.value.id ==
            list_var and stmt.value.func.attr == "append" and len(stmt.
            value.args) == 1):
            return True
        return bool(isinstance(stmt, ast.If) and len(stmt.body) == 1 and
            len(stmt.orelse) == 0 and isinstance(stmt.body[0], ast.Expr) and
            isinstance(stmt.body[0].value, ast.Call) and isinstance(stmt.
            body[0].value.func, ast.Attribute) and isinstance(stmt.body[0].
            value.func.value, ast.Name) and stmt.body[0].value.func.value.
            id == list_var and stmt.body[0].value.func.attr == "append" and
            len(stmt.body[0].value.args) == 1)


        # Check for conditional append
        return bool(isinstance(stmt, ast.If) and len(stmt.body) == 1 and len(stmt.orelse) == 0 and isinstance(stmt.body[0], ast.Expr) and isinstance(stmt.body[0].value, ast.Call) and isinstance(stmt.body[0].value.func, ast.Attribute) and isinstance(stmt.body[0].value.func.value, ast.Name) and stmt.body[0].value.func.value.id == list_var and stmt.body[0].value.func.attr == "append" and len(stmt.body[0].value.args) == 1)
    def _create_list_comprehension(self, for_node, list_var):
=======
    @staticmethod
    def _create_list_comprehension(for_node, list_var):
>>>>>>> origin/main
        """Create a list comprehension from a for loop."""
        stmt = for_node.body[0]
        if isinstance(stmt, ast.Expr):
            elt = stmt.value.args[0]
            return ast.ListComp(elt=elt, generators=[ast.comprehension(
                target=for_node.target, iter=for_node.iter, ifs=[],
                is_async=False)])
        if isinstance(stmt, ast.If):
            elt = stmt.body[0].value.args[0]
            return ast.ListComp(elt=elt, generators=[ast.comprehension(
                target=for_node.target, iter=for_node.iter, ifs=[stmt.test],
                is_async=False)])
        return None


def fix_perf401_in_file(file_path: Path) -> bool:
    """Fix PERF401 issues in a file using AST."""
    try:
        with Path(file_path).open("r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return False
    transformer = ListComprehensionTransformer()
    new_tree = transformer.visit(tree)
    if transformer.changes_made:
        try:
            import astor
            new_content = astor.to_source(new_tree)
            with Path(file_path).open("w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False
    return False


def main():
    """Main function to fix PERF401 issues."""
    try:
        import astor
    except ImportError:
        print("Installing astor for AST to source conversion...")
        os.system("uv pip install astor")
    python_files = []
    for pattern in ["**/*.py"]:
        python_files.extend(Path().glob(pattern))
    exclude_dirs = {".git", ".mypy_cache", ".ruff_cache", ".venv",
        "__pycache__", "build", "dist", ".claude", "grammars", "archive",
        "worktrees", "flask", "rust", "click", "gin", "guava", "googletest",
        "lodash", "ruby", "serde", "TypeScript"}
    python_files = [f for f in python_files if not any(exc in f.parts for
        exc in exclude_dirs)]
    fixed_count = 0
    for file_path in python_files:
        if fix_perf401_in_file(file_path):
            fixed_count += 1
            print(f"Fixed {file_path}")
    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
