"""JavaScript-specific context extraction implementation."""

from tree_sitter import Node

from ...interfaces.context import ContextItem, ContextType
from ..extractor import BaseContextExtractor
from ..filter import BaseContextFilter
from ..scope_analyzer import BaseScopeAnalyzer
from ..symbol_resolver import BaseSymbolResolver


class JavaScriptContextExtractor(BaseContextExtractor):
    """JavaScript-specific context extraction."""

    def __init__(self):
        """Initialize JavaScript context extractor."""
        super().__init__("javascript")

    def _is_import_node(self, node: Node) -> bool:
        """Check if a node represents an import statement."""
        return node.type == "import_statement"

    def _is_type_definition_node(self, node: Node) -> bool:
        """Check if a node represents a type definition."""
        # JavaScript classes and interfaces (in JSDoc or TypeScript mode)
        return node.type in ("class_declaration", "interface_declaration")

    def _is_scope_node(self, node: Node) -> bool:
        """Check if a node represents a scope."""
        # Check if it's an arrow function assigned to a const
        if node.type == "variable_declarator":
            for child in node.children:
                if child.type == "arrow_function":
                    return True

        return node.type in (
            "function_declaration",
            "function_expression",
            "arrow_function",
            "class_declaration",
            "method_definition",
            "program",
            "variable_declarator",
        )

    def _is_decorator_node(self, node: Node) -> bool:
        """Check if a node represents a decorator."""
        # JavaScript decorators (stage 3 proposal)
        return node.type == "decorator"

    def _extract_type_declaration(self, node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a type definition."""
        if node.type == "class_declaration":
            # Find the class body
            for child in node.children:
                if child.type == "class_body":
                    # Stop before the body
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    # Add ellipsis to indicate body was truncated
                    return declaration + " { ... }"

            # If no body found, return the whole thing
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()

        if node.type == "interface_declaration":
            # Similar handling for interfaces
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

    def _extract_scope_declaration(self, node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a scope."""
        if node.type == "function_declaration":
            # Find the function body
            for child in node.children:
                if child.type == "statement_block":
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return declaration + " { ... }"

            return (
                source[node.start_byte : node.end_byte]
                .decode("utf-8")
                .split("{")[0]
                .strip()
                + " { ... }"
            )

        if node.type in ("function_expression", "arrow_function"):
            # For function expressions and arrow functions
            for child in node.children:
                if child.type in ("statement_block", "=>"):
                    end_byte = (
                        child.start_byte
                        if child.type == "statement_block"
                        else child.end_byte
                    )
                    declaration = (
                        source[node.start_byte : end_byte].decode("utf-8").strip()
                    )
                    if child.type == "=>":
                        return declaration + " ..."
                    return declaration + " { ... }"

            return (
                source[node.start_byte : node.end_byte]
                .decode("utf-8")
                .split("{")[0]
                .strip()
            )

        if node.type == "method_definition":
            # Extract method signature
            for child in node.children:
                if child.type == "statement_block":
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return declaration + " { ... }"

            return (
                source[node.start_byte : node.end_byte]
                .decode("utf-8")
                .split("{")[0]
                .strip()
                + " { ... }"
            )

        if node.type == "class_declaration":
            return self._extract_type_declaration(node, source)

        if node.type == "variable_declarator":
            # Handle const/let/var declarations
            # Get the parent declaration to include const/let/var
            parent = node.parent
            if parent and parent.type in (
                "lexical_declaration",
                "variable_declaration",
            ):
                # Find where the value starts
                for child in node.children:
                    if child.type == "=":
                        # Include up to and including the =
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

    def _find_references_in_node(
        self,
        node: Node,
        source: bytes,
    ) -> list[tuple[str, Node]]:
        """Find all identifier references in a node."""
        references = []

        def find_identifiers(n: Node):
            if n.type == "identifier":
                # Check if this is a reference (not a definition)
                parent = n.parent
                if parent and not self._is_definition_context(n):
                    name = source[n.start_byte : n.end_byte].decode("utf-8")
                    references.append((name, n))

            # Also check member expressions
            elif n.type == "member_expression":
                # Get the object being accessed
                for child in n.children:
                    if child.type == "identifier":
                        name = source[child.start_byte : child.end_byte].decode("utf-8")
                        references.append((name, child))
                        break

            # Recurse
            for child in n.children:
                find_identifiers(child)

        find_identifiers(node)
        return references

    def _is_definition_context(self, identifier_node: Node) -> bool:
        """Check if an identifier is in a definition context."""
        parent = identifier_node.parent
        if not parent:
            return False

        # Function/class names
        if parent.type in ("function_declaration", "class_declaration"):
            # Check if this is the name of the definition
            for i, child in enumerate(parent.children):
                if child == identifier_node and i < 2:  # Name usually comes early
                    return True

        # Variable declarations
        if parent.type in (
            "variable_declarator",
            "const_declaration",
            "let_declaration",
        ):
            # Check if this is the variable name
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type == "=":
                    break

        # Parameters
        if parent.type in ("formal_parameters", "rest_pattern", "identifier"):
            grandparent = parent.parent
            if grandparent and grandparent.type in (
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            ):
                return True

        # Object property definitions
        if (
            parent.type == "property_identifier"
            or parent.type == "shorthand_property_identifier"
        ):
            grandparent = parent.parent
            if grandparent and grandparent.type in ("object", "object_pattern"):
                return True

        # Import specifiers
        if parent.type in ("import_specifier", "namespace_import"):
            return True

        return False

    def _find_definition(
        self,
        name: str,
        scope_node: Node,
        ast: Node,
        source: bytes,
    ) -> ContextItem | None:
        """Find the definition of a name."""
        # Use the symbol resolver to find the definition
        resolver = JavaScriptSymbolResolver()
        def_node = resolver.find_symbol_definition(name, scope_node, ast)

        if def_node:
            # Extract the definition
            content = source[def_node.start_byte : def_node.end_byte].decode("utf-8")
            line_number = source[: def_node.start_byte].count(b"\n") + 1

            # Determine the context type
            context_type = ContextType.DEPENDENCY
            if def_node.type == "class_declaration":
                context_type = ContextType.TYPE_DEF
                content = self._extract_type_declaration(def_node, source)
            elif def_node.type in (
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            ):
                content = self._extract_scope_declaration(def_node, source)

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

    def _get_node_type_map(self) -> dict[str, str]:
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
            "identifier": "variable",  # In parameter context
            "import_statement": "import",
        }

    def _is_identifier_node(self, node: Node) -> bool:
        """Check if a node is an identifier."""
        return node.type == "identifier"

    def _is_definition_node(self, node: Node) -> bool:
        """Check if a node defines a symbol."""
        return node.type in (
            "function_declaration",
            "class_declaration",
            "variable_declarator",
            "const_declaration",
            "let_declaration",
            "method_definition",
            "function_expression",
            "arrow_function",
        )

    def _is_definition_context(self, node: Node) -> bool:
        """Check if an identifier node is in a definition context."""
        # Reuse the implementation from JavaScriptContextExtractor
        extractor = JavaScriptContextExtractor()
        return extractor._is_definition_context(node)

    def _get_defined_name(self, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        if node.type in ("function_declaration", "class_declaration"):
            # Name is typically the first or second identifier child
            for child in node.children:
                if child.type == "identifier":
                    # Would need source bytes to get actual text
                    return None  # Placeholder

        elif node.type == "variable_declarator":
            # Get the identifier on the left side
            for child in node.children:
                if child.type == "identifier":
                    return None  # Placeholder
                if child.type == "=":
                    break

        elif node.type == "method_definition":
            # Method name
            for child in node.children:
                if child.type == "property_identifier":
                    return None  # Placeholder

        return None

    def _creates_new_scope(self, node: Node) -> bool:
        """Check if a node creates a new scope."""
        return node.type in (
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
        )


class JavaScriptScopeAnalyzer(BaseScopeAnalyzer):
    """JavaScript-specific scope analysis."""

    def __init__(self):
        """Initialize JavaScript scope analyzer."""
        super().__init__("javascript")

    def _get_scope_type_map(self) -> dict[str, str]:
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

    def _is_definition_node(self, node: Node) -> bool:
        """Check if a node defines a symbol."""
        resolver = JavaScriptSymbolResolver()
        return resolver._is_definition_node(node)

    def _is_import_node(self, node: Node) -> bool:
        """Check if a node is an import statement."""
        return node.type == "import_statement"

    def _get_defined_name(self, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        resolver = JavaScriptSymbolResolver()
        return resolver._get_defined_name(node)

    def _extract_imported_names(self, import_node: Node) -> set[str]:
        """Extract symbol names from an import node."""
        names = set()

        if import_node.type == "import_statement":
            for child in import_node.children:
                if child.type == "import_clause":
                    # Handle various import patterns
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            # Default import
                            pass
                        elif subchild.type == "namespace_import":
                            # import * as name
                            for name_child in subchild.children:
                                if name_child.type == "identifier":
                                    pass
                        elif subchild.type == "named_imports":
                            # import { a, b } from
                            for import_spec in subchild.children:
                                if import_spec.type == "import_specifier":
                                    # Could be { a } or { a as b }
                                    for spec_child in import_spec.children:
                                        if spec_child.type == "identifier":
                                            # Would need to check if it's after 'as'
                                            pass

        return names


class JavaScriptContextFilter(BaseContextFilter):
    """JavaScript-specific context filtering."""

    def __init__(self):
        """Initialize JavaScript context filter."""
        super().__init__("javascript")

    def _is_decorator_node(self, node: Node) -> bool:
        """Check if a node is a decorator."""
        return node.type == "decorator"
