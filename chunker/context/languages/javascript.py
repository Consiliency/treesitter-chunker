"""JavaScript-specific context extraction implementation."""

from tree_sitter import Node

from chunker.context.extractor import BaseContextExtractor
from chunker.context.filter import BaseContextFilter
from chunker.context.scope_analyzer import BaseScopeAnalyzer
from chunker.context.symbol_resolver import BaseSymbolResolver
from chunker.interfaces.context import ContextItem, ContextType


class JavaScriptContextExtractor(BaseContextExtractor):
    """JavaScript-specific context extraction."""

    def __init__(self):
        """Initialize JavaScript context extractor."""
        super().__init__("javascript")

    @staticmethod
    def _is_import_node(node: Node) -> bool:
        """Check if a node represents an import statement."""
        return node.type == "import_statement"

    @staticmethod
    def _is_type_definition_node(node: Node) -> bool:
        """Check if a node represents a type definition."""
        return node.type in {"class_declaration", "interface_declaration"}

    @staticmethod
    def _is_scope_node(node: Node) -> bool:
        """Check if a node represents a scope."""
        if node.type == "variable_declarator":
            for child in node.children:
                if child.type == "arrow_function":
                    return True
        return node.type in {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "method_definition",
            "program",
            "variable_declarator",
        }

    @staticmethod
    def _is_decorator_node(node: Node) -> bool:
        """Check if a node represents a decorator."""
        return node.type == "decorator"

    @staticmethod
    def _extract_type_declaration(node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a type definition."""
        if node.type == "class_declaration":
            for child in node.children:
                if child.type == "class_body":
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return declaration + " { ... }"
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()
        if node.type == "interface_declaration":
            for child in node.children:
                if child.type == "interface_body":
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return declaration + " { ... }"
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()
        return None

    @staticmethod
    def _extract_scope_declaration(node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a scope."""
        extraction_methods = {
            "function_declaration": JavaScriptContextExtractor._extract_function_declaration,
            "function_expression": JavaScriptContextExtractor._extract_function_expression,
            "arrow_function": JavaScriptContextExtractor._extract_function_expression,
            "method_definition": JavaScriptContextExtractor._extract_method_definition,
            "class_declaration": JavaScriptContextExtractor._extract_class_declaration,
            "constructor_definition": JavaScriptContextExtractor._extract_constructor_definition,
        }

        extractor = extraction_methods.get(node.type)
        if extractor:
            return extractor(node, source)

        # Default extraction for unknown types
        if node.type == "method_definition":
            parent = node.parent
            if parent and parent.type in {
                "variable_declarator",
                "assignment_expression",
                "pair",
                "variable_declaration",
            }:
                for child in node.children:
                    if child.type == "=":
                        declaration = (
                            source[parent.start_byte : child.end_byte]
                            .decode("utf-8")
                            .strip()
                        )
                        return declaration + " ..."
            return (
                source[node.start_byte : node.end_byte]
                .decode("utf-8")
                .split("=")[0]
                .strip()
                + " = ..."
            )
        return None

    @staticmethod
    def _extract_function_declaration(node: Node, source: bytes) -> str:
        """Extract function declaration."""
        for child in node.children:
            if child.type == "statement_block":
                declaration = (
                    source[node.start_byte : child.start_byte].decode("utf-8").strip()
                )
                return declaration + " { ... }"
        return (
            source[node.start_byte : node.end_byte]
            .decode("utf-8")
            .split("{")[0]
            .strip()
            + " { ... }"
        )

    @staticmethod
    def _extract_function_expression(node: Node, source: bytes) -> str:
        """Extract function expression or arrow function."""
        for child in node.children:
            if child.type in {"statement_block", "=>"}:
                end_byte = (
                    child.start_byte
                    if child.type == "statement_block"
                    else child.end_byte
                )
                declaration = source[node.start_byte : end_byte].decode("utf-8").strip()
                if child.type == "=>":
                    return declaration + " ..."
                return declaration + " { ... }"
        return (
            source[node.start_byte : node.end_byte]
            .decode("utf-8")
            .split("{")[0]
            .strip()
        )

    @staticmethod
    def _extract_method_definition(node: Node, source: bytes) -> str:
        """Extract method definition."""
        for child in node.children:
            if child.type == "statement_block":
                declaration = (
                    source[node.start_byte : child.start_byte].decode("utf-8").strip()
                )
                return declaration + " { ... }"
        return source[node.start_byte : node.end_byte].decode("utf-8").strip()

    @staticmethod
    def _extract_class_declaration(node: Node, source: bytes) -> str:
        """Extract class declaration."""
        for child in node.children:
            if child.type == "class_body":
                declaration = (
                    source[node.start_byte : child.start_byte].decode("utf-8").strip()
                )
                return declaration + " { ... }"
        return source[node.start_byte : node.end_byte].decode("utf-8").strip()

    @staticmethod
    def _extract_constructor_definition(node: Node, source: bytes) -> str:
        """Extract constructor definition."""
        return JavaScriptContextExtractor._extract_method_definition(node, source)

    def _find_references_in_node(
        self,
        node: Node,
        source: bytes,
    ) -> list[tuple[str, Node]]:
        """Find all identifier references in a node."""
        references = []

        def find_identifiers(n: Node):
            if n.type == "identifier":
                parent = n.parent
                if parent and not self._is_definition_context(n):
                    name = source[n.start_byte : n.end_byte].decode("utf-8")
                    references.append((name, n))
            elif n.type == "member_expression":
                for child in n.children:
                    if child.type == "identifier":
                        name = source[child.start_byte : child.end_byte].decode("utf-8")
                        references.append((name, child))
                        break
            for child in n.children:
                find_identifiers(child)

        find_identifiers(node)
        return references

    @staticmethod
    def _is_definition_context(identifier_node: Node) -> bool:
        """Check if an identifier is in a definition context."""
        parent = identifier_node.parent
        if not parent:
            return False
        if parent.type in {"function_declaration", "class_declaration"}:
            for i, child in enumerate(parent.children):
                if child == identifier_node and i < 2:
                    return True
        if parent.type in {
            "variable_declarator",
            "const_declaration",
            "let_declaration",
        }:
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type == "=":
                    break
        if parent.type in {"formal_parameters", "rest_pattern", "identifier"}:
            grandparent = parent.parent
            if grandparent and grandparent.type in {
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            }:
                return True
        if parent.type in {"property_identifier", "shorthand_property_identifier"}:
            grandparent = parent.parent
            if grandparent and grandparent.type in {
                "object",
                "object_pattern",
            }:
                return True
        return parent.type in {"import_specifier", "namespace_import"}

    def _find_definition(
        self,
        name: str,
        scope_node: Node,
        ast: Node,
        source: bytes,
    ) -> ContextItem | None:
        """Find the definition of a name."""
        resolver = JavaScriptSymbolResolver()
        def_node = resolver.find_symbol_definition(name, scope_node, ast)
        if def_node:
            content = source[def_node.start_byte : def_node.end_byte].decode("utf-8")
            line_number = source[: def_node.start_byte].count(b"\n") + 1
            context_type = ContextType.DEPENDENCY
            if def_node.type == "class_declaration":
                context_type = ContextType.TYPE_DEF
                content = self._extract_type_declaration(def_node, source)
            elif def_node.type in {
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            }:
                content = JavaScriptContextExtractor._extract_scope_declaration(
                    def_node,
                    source,
                )
            return ContextItem(
                type=context_type,
                content=content,
                node=def_node,
                line_number=line_number,
                importance=60,
            )
        return None


class JavaScriptSymbolResolver(BaseSymbolResolver):
    """JavaScript-specific symbol resolution."""

    def __init__(self):
        """Initialize JavaScript symbol resolver."""
        super().__init__("javascript")

    @staticmethod
    def _get_node_type_map() -> dict[str, str]:
        """Get mapping from AST node types to symbol types."""
        return {
            "function_declaration": "function",
            "function_expression": "function",
            "arrow_function": "function",
            "class_declaration": "class",
            "method_definition": "method",
            "variable_declarator": "variable",
            "const_declaration": "constant",
            "let_declaration": "variable",
            "identifier": "variable",
            "import_statement": "import",
        }

    @staticmethod
    def _is_identifier_node(node: Node) -> bool:
        """Check if a node is an identifier."""
        return node.type == "identifier"

    @staticmethod
    def _is_definition_node(node: Node) -> bool:
        """Check if a node defines a symbol."""
        return node.type in {
            "function_declaration",
            "class_declaration",
            "variable_declarator",
            "const_declaration",
            "let_declaration",
            "method_definition",
            "function_expression",
            "arrow_function",
        }

    @classmethod
    def _is_definition_context(cls, node: Node) -> bool:
        """Check if an identifier node is in a definition context."""
        extractor = JavaScriptContextExtractor()
        return extractor._is_definition_context(node)

    @staticmethod
    def _get_defined_name(node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        if node.type in {"function_declaration", "class_declaration"}:
            for child in node.children:
                if child.type == "identifier":
                    return None
        elif node.type == "variable_declarator":
            for child in node.children:
                if child.type == "identifier":
                    return None
                if child.type == "=":
                    break
        elif node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return None
        return None

    @staticmethod
    def _creates_new_scope(node: Node) -> bool:
        """Check if a node creates a new scope."""
        return node.type in {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "method_definition",
            "for_statement",
            "for_in_statement",
            "for_of_statement",
            "block_statement",
            "catch_clause",
        }


class JavaScriptScopeAnalyzer(BaseScopeAnalyzer):
    """JavaScript-specific scope analysis."""

    def __init__(self):
        """Initialize JavaScript scope analyzer."""
        super().__init__("javascript")

    @staticmethod
    def _get_scope_type_map() -> dict[str, str]:
        """Get mapping from AST node types to scope types."""
        return {
            "program": "module",
            "function_declaration": "function",
            "function_expression": "function",
            "arrow_function": "arrow",
            "class_declaration": "class",
            "method_definition": "method",
            "for_statement": "block",
            "for_in_statement": "block",
            "for_of_statement": "block",
            "block_statement": "block",
            "catch_clause": "catch",
        }

    def _is_scope_node(self, node: Node) -> bool:
        """Check if a node creates a scope."""
        return node.type in self._get_scope_type_map()

    @classmethod
    def _is_definition_node(cls, node: Node) -> bool:
        """Check if a node defines a symbol."""
        resolver = JavaScriptSymbolResolver()
        return resolver._is_definition_node(node)

    @staticmethod
    def _is_import_node(node: Node) -> bool:
        """Check if a node is an import statement."""
        return node.type == "import_statement"

    @classmethod
    def _get_defined_name(cls, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        resolver = JavaScriptSymbolResolver()
        return resolver._get_defined_name(node)

    @staticmethod
    def _extract_imported_names(import_node: Node) -> set[str]:
        """Extract symbol names from an import node."""
        names = set()
        if import_node.type != "import_statement":
            return names

        for child in import_node.children:
            if child.type == "import_clause":
                names.update(
                    JavaScriptContextExtractor._extract_from_import_clause(child),
                )
        return names

    @staticmethod
    def _extract_from_import_clause(import_clause: Node) -> set[str]:
        """Extract names from import clause."""
        names = set()
        for child in import_clause.children:
            if child.type == "identifier":
                # Default import: import foo from 'module'
                names.add(child.text.decode("utf-8") if child.text else "")
            elif child.type == "namespace_import":
                # Namespace import: import * as foo from 'module'
                names.update(
                    JavaScriptContextExtractor._extract_namespace_import(child),
                )
            elif child.type == "named_imports":
                # Named imports: import { foo, bar } from 'module'
                names.update(JavaScriptContextExtractor._extract_named_imports(child))
        return names

    @staticmethod
    def _extract_namespace_import(namespace_node: Node) -> set[str]:
        """Extract names from namespace import."""
        names = set()
        for child in namespace_node.children:
            if child.type == "identifier":
                names.add(child.text.decode("utf-8") if child.text else "")
        return names

    @staticmethod
    def _extract_named_imports(named_imports_node: Node) -> set[str]:
        """Extract names from named imports."""
        names = set()
        for child in named_imports_node.children:
            if child.type == "import_specifier":
                # Get the local name (or imported name if no 'as' clause)
                for spec_child in child.children:
                    if spec_child.type == "identifier":
                        names.add(
                            spec_child.text.decode("utf-8") if spec_child.text else "",
                        )
                        break  # Only need the first identifier (imported name)
        return names


class JavaScriptContextFilter(BaseContextFilter):
    """JavaScript-specific context filtering."""

    def __init__(self):
        """Initialize JavaScript context filter."""
        super().__init__("javascript")

    @staticmethod
    def _is_decorator_node(node: Node) -> bool:
        """Check if a node is a decorator."""
        return node.type == "decorator"
