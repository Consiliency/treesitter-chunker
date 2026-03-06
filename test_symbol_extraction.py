#!/usr/bin/env python3
"""Test script for symbol extraction (standalone, minimal dependencies)."""

import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SymbolDefinition:
    """Represents a symbol definition (class, function, method)."""
    name: str
    kind: str
    file: str
    line: int
    end_line: int
    module: str = ""
    parent_class: str = ""
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "module": self.module,
            "parent_class": self.parent_class,
            "bases": self.bases,
            "decorators": self.decorators,
            "docstring": self.docstring,
        }


@dataclass
class ImportDefinition:
    """Represents an import statement."""
    module: str
    names: list[str]
    alias: str = ""
    line: int = 0
    is_from_import: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "names": self.names,
            "alias": self.alias,
            "line": self.line,
            "is_from_import": self.is_from_import,
        }


@dataclass
class SymbolRelationship:
    """Represents a relationship between symbols."""
    from_symbol: str
    to_symbol: str
    kind: str
    line: int
    file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_symbol,
            "to": self.to_symbol,
            "type": self.kind,
            "line": self.line,
            "file": self.file,
        }


class SimpleSymbolVisitor(ast.NodeVisitor):
    """Simple AST visitor for symbol extraction."""

    def __init__(self, source_code: str, file_path: str = "<string>", module_name: str = ""):
        self.source_code = source_code
        self.file_path = file_path
        self.module_name = module_name or Path(file_path).stem if file_path != "<string>" else "module"

        self.symbols: dict[str, list] = {"classes": [], "functions": []}
        self.imports: list[ImportDefinition] = []
        self.relationships: list[SymbolRelationship] = []

        self.class_stack: list[str] = []
        self.function_stack: list[str] = []

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        if isinstance(decorator, ast.Name):
            return decorator.id
        if isinstance(decorator, ast.Attribute):
            parts = []
            node = decorator
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        if isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func) + "(...)"
        return str(type(decorator).__name__)

    def _get_base_name(self, base: ast.AST) -> str:
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            parts = []
            node = base
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        return str(type(base).__name__)

    def _get_current_qualified_name(self) -> str:
        parts = [self.module_name]
        if self.class_stack:
            parts.append(self.class_stack[-1])
        if self.function_stack:
            if len(parts) > 1:
                return f"{parts[0]}:{parts[1]}.{self.function_stack[-1]}"
            return f"{parts[0]}:{self.function_stack[-1]}"
        if len(parts) > 1:
            return f"{parts[0]}:{parts[1]}"
        return parts[0]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                ImportDefinition(
                    module=alias.name,
                    names=[],
                    alias=alias.asname or "",
                    line=node.lineno,
                    is_from_import=False,
                )
            )
            self.relationships.append(
                SymbolRelationship(
                    from_symbol=self.module_name,
                    to_symbol=alias.name,
                    kind="imports",
                    line=node.lineno,
                    file=self.file_path,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            names = [alias.asname if alias.asname else alias.name for alias in node.names]
            self.imports.append(
                ImportDefinition(
                    module=node.module,
                    names=names,
                    alias="",
                    line=node.lineno,
                    is_from_import=True,
                )
            )
            self.relationships.append(
                SymbolRelationship(
                    from_symbol=self.module_name,
                    to_symbol=node.module,
                    kind="imports",
                    line=node.lineno,
                    file=self.file_path,
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [self._get_base_name(base) for base in node.bases]
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        docstring = ""
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value[:200]

        symbol = SymbolDefinition(
            name=node.name,
            kind="class",
            file=self.file_path,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            module=self.module_name,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
        )
        self.symbols["classes"].append(symbol)

        # Track inheritance relationships
        qualified_class = f"{self.module_name}:{node.name}"
        for base in bases:
            self.relationships.append(
                SymbolRelationship(
                    from_symbol=qualified_class,
                    to_symbol=base,
                    kind="inherits",
                    line=node.lineno,
                    file=self.file_path,
                )
            )

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node, is_async: bool = False) -> None:
        is_method = len(self.class_stack) > 0
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        if is_async:
            decorators = ["async"] + decorators

        docstring = ""
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value[:200]

        parent_class = self.class_stack[-1] if is_method else ""

        symbol = SymbolDefinition(
            name=node.name,
            kind="method" if is_method else "function",
            file=self.file_path,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            module=self.module_name,
            parent_class=parent_class,
            decorators=decorators,
            docstring=docstring,
        )
        self.symbols["functions"].append(symbol)

        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        # Extract function name
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            n = node.func
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if isinstance(n, ast.Name):
                parts.append(n.id)
            func_name = ".".join(reversed(parts))

        if func_name:
            from_symbol = self._get_current_qualified_name()
            self.relationships.append(
                SymbolRelationship(
                    from_symbol=from_symbol,
                    to_symbol=func_name,
                    kind="calls",
                    line=node.lineno,
                    file=self.file_path,
                )
            )

        self.generic_visit(node)


def extract_symbols(source_code: str, file_path: str = "<string>", module_name: str = "") -> dict:
    """Extract symbols from Python source code."""
    result = {
        "symbols": {"classes": [], "functions": [], "imports": []},
        "relationships": [],
        "metadata": {},
        "errors": [],
    }

    try:
        tree = ast.parse(source_code, filename=file_path)
        visitor = SimpleSymbolVisitor(source_code, file_path, module_name)
        visitor.visit(tree)

        result["symbols"] = {
            "classes": [s.to_dict() for s in visitor.symbols["classes"]],
            "functions": [s.to_dict() for s in visitor.symbols["functions"]],
            "imports": [i.to_dict() for i in visitor.imports],
        }
        result["relationships"] = [r.to_dict() for r in visitor.relationships]
        result["metadata"] = {
            "file": file_path,
            "module": visitor.module_name,
            "source_lines": len(source_code.splitlines()),
            "class_count": len(visitor.symbols["classes"]),
            "function_count": len(visitor.symbols["functions"]),
            "import_count": len(visitor.imports),
            "relationship_count": len(visitor.relationships),
        }
    except SyntaxError as e:
        result["errors"].append(f"Syntax error: {e}")
    except Exception as e:
        result["errors"].append(f"Error: {e}")

    return result


def extract_from_directory(path: Path, output_file: str | None = None) -> dict:
    """Extract symbols from all Python files in a directory."""
    files = list(path.rglob("*.py"))
    files = [
        f for f in files
        if not any(part in f.parts for part in [
            "__pycache__", ".git", ".venv", "venv", "node_modules",
            ".tox", ".pytest_cache", "build", "dist", ".eggs"
        ])
    ]

    all_symbols: dict[str, list] = {"classes": [], "functions": [], "imports": []}
    all_relationships: list[dict] = []
    metadata = {
        "files_processed": 0,
        "total_classes": 0,
        "total_functions": 0,
        "total_imports": 0,
        "total_relationships": 0,
        "errors": [],
    }

    for file_path in sorted(files):
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            metadata["errors"].append(f"Error reading {file_path}: {e}")
            continue

        try:
            rel_path = file_path.relative_to(path)
            module_parts = list(rel_path.parts)
            if module_parts[-1].endswith(".py"):
                module_parts[-1] = module_parts[-1][:-3]
            module_name = ".".join(module_parts)
        except ValueError:
            module_name = file_path.stem

        result = extract_symbols(source_code, str(file_path), module_name)

        if result["errors"]:
            metadata["errors"].extend(result["errors"])
            continue

        all_symbols["classes"].extend(result["symbols"]["classes"])
        all_symbols["functions"].extend(result["symbols"]["functions"])
        all_symbols["imports"].extend(result["symbols"]["imports"])
        all_relationships.extend(result["relationships"])
        metadata["files_processed"] += 1

    metadata["total_classes"] = len(all_symbols["classes"])
    metadata["total_functions"] = len(all_symbols["functions"])
    metadata["total_imports"] = len(all_symbols["imports"])
    metadata["total_relationships"] = len(all_relationships)

    output = {
        "symbols": all_symbols,
        "relationships": all_relationships,
        "metadata": metadata,
    }

    if output_file:
        Path(output_file).write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    return output


if __name__ == "__main__":
    # Test with sample code
    code = '''
import os
from typing import List

class MyClass:
    """A sample class."""
    def my_method(self, x: int) -> int:
        return x + 1

def helper(y: str) -> str:
    """Helper function."""
    return y.upper()

result = helper("test")
'''

    result = extract_symbols(code)
    print(json.dumps(result, indent=2))

    # Test with command line args
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        output = sys.argv[2] if len(sys.argv) > 2 else None

        if path.is_file():
            result = extract_symbols(path.read_text(), str(path), path.stem)
        else:
            result = extract_from_directory(path, output)

        if not output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Extracted symbols from {result['metadata']['files_processed']} files")
            print(f"  Classes: {result['metadata']['total_classes']}")
            print(f"  Functions: {result['metadata']['total_functions']}")
            print(f"  Imports: {result['metadata']['total_imports']}")
            print(f"  Relationships: {result['metadata']['total_relationships']}")
            print(f"Output written to: {output}")
