"""Fix PLR6301 errors - methods that could be static/class methods."""
import ast
import subprocess
from pathlib import Path


class MethodAnalyzer(ast.NodeVisitor):
    """Analyze methods to determine if they should be static/class methods."""

    def __init__(self):
        self.methods_to_fix = []
        self.current_class = None

    def visit_ClassDef(self, node):
        """Visit class definition."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        """Visit function definition."""
        if self.current_class and node.args.args:
            first_arg = node.args.args[0].arg
            if first_arg in ("self", "cls"):
                uses_self = self._uses_self(node, first_arg)
                if not uses_self:
                    uses_class_features = self._uses_class_features(node)
                    self.methods_to_fix.append({"class": self.current_class,
                        "method": node.name, "line": node.lineno, "type":
                        "classmethod" if uses_class_features else
                        "staticmethod", "first_arg": first_arg})
        self.generic_visit(node)

    @staticmethod
    def _uses_self(node, param_name):
        """Check if self/cls parameter is used in method body."""

        class SelfChecker(ast.NodeVisitor):

            def __init__(self, param_name):
                self.param_name = param_name
                self.uses_self = False

            def visit_Name(self, node):
                if node.id == self.param_name:
                    self.uses_self = True
        checker = SelfChecker(param_name)
        checker.visit(node)
        return checker.uses_self

    @staticmethod
    def _uses_class_features(node):
        """Check if method uses class-level features (suggesting classmethod)."""

        class ClassFeatureChecker(ast.NodeVisitor):

            def __init__(self):
                self.uses_class_features = False

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id[0].isupper(
                    ):
                    self.uses_class_features = True
                self.generic_visit(node)
        checker = ClassFeatureChecker()
        checker.visit(node)
        return checker.uses_class_features


def fix_plr6301_in_file(file_path: Path) -> bool:
    """Fix PLR6301 errors in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        try:
            tree = ast.parse(content)
        except SyntaxError:
            print(f"Syntax error in {file_path}, skipping")
            return False
        analyzer = MethodAnalyzer()
        analyzer.visit(tree)
        if not analyzer.methods_to_fix:
            return False
        lines = content.split("\n")
        for fix in sorted(analyzer.methods_to_fix, key=lambda x: x["line"],
            reverse=True):
            method_line = fix["line"] - 1
            for i in range(max(0, method_line - 5), min(len(lines),
                method_line + 5)):
                if f"def {fix['method']}" in lines[i]:
                    method_line = i
                    break
            if method_line > 0:
                prev_line = lines[method_line - 1].strip()
                if "@staticmethod" in prev_line or "@classmethod" in prev_line:
                    continue
            indent = len(lines[method_line]) - len(lines[method_line].lstrip())
            decorator_indent = " " * indent
            decorator = f"{decorator_indent}@{fix['type']}"
            insert_line = method_line
            for j in range(method_line - 1, -1, -1):
                if lines[j].strip().startswith("@"):
                    insert_line = j
                elif lines[j].strip():
                    break
            lines.insert(insert_line, decorator)
        new_content = "\n".join(lines)
        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Find and fix PLR6301 errors."""
    result = subprocess.run(["ruff", "check", "--select", "PLR6301", ".",
        "--output-format", "json"], capture_output=True, text=True, check=False,
        )
    if result.returncode == 0:
        print("No PLR6301 errors found!")
        return
    files_to_fix = set()
    for line in result.stdout.splitlines():
        if "PLR6301" in line and ".py:" in line:
            file_path = line.split(":")[0].strip()
            files_to_fix.add(file_path)
    if not files_to_fix:
        result = subprocess.run(["ruff", "check", "--select", "PLR6301",
            "."], capture_output=True, text=True, check=False)
        for line in result.stdout.splitlines():
            if "PLR6301" in line and ".py:" in line:
                file_path = line.split(":")[0].strip()
                files_to_fix.add(file_path)
    fixed = 0
    for file_path in sorted(files_to_fix):
        path = Path(file_path)
        if path.exists() and fix_plr6301_in_file(path):
            print(f"Fixed: {file_path}")
            fixed += 1
    print(f"\nFixed {fixed} files")


if __name__ == "__main__":
    main()
