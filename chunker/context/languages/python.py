"""Python-specific context extraction implementation."""

from tree_sitter import Node

from chunker.context.extractor import BaseContextExtractor
from chunker.context.filter import BaseContextFilter
from chunker.context.scope_analyzer import BaseScopeAnalyzer
from chunker.context.symbol_resolver import BaseSymbolResolver
from chunker.interfaces.context import ContextItem, ContextType


class PythonContextExtractor(BaseContextExtractor):
    """Python-specific context extraction."""

    def __init__(self):
        """Initialize Python context extractor."""
        super().__init__("python")

    def _is_import_node(self, node: Node) -> bool:
        """Check if a node represents an import statement."""
        return node.type in ("import_statement", "import_from_statement")

    def _is_type_definition_node(self, node: Node) -> bool:
        """Check if a node represents a type definition."""
        return node.type in ("class_definition", "type_alias")

    def _is_scope_node(self, node: Node) -> bool:
        """Check if a node represents a scope."""
        return node.type in ("function_definition", "class_definition", "module")

    def _is_decorator_node(self, node: Node) -> bool:
        """Check if a node represents a decorator."""
        return node.type == "decorator"

    def _extract_type_declaration(self, node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a type definition."""
        if node.type == "class_definition":
            # Find the class name and base classes
            for child in node.children:
                if child.type == "block":
                    # Stop before the body
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    # Add ellipsis to indicate body was truncated
                    return declaration + " ..."

            # If no body found, return the whole thing
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()

        if node.type == "type_alias":
            # Return the full type alias
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()

        return None

    def _extract_scope_declaration(self, node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a scope."""
        if node.type == "function_definition":
            # Find the function signature (up to the colon)
            for child in node.children:
                if child.type == ":":
                    declaration = (
                        source[node.start_byte : child.end_byte].decode("utf-8").strip()
                    )
                    return declaration

            # Fallback
            return (
                source[node.start_byte : node.end_byte].decode("utf-8").split("\n")[0]
            )

        if node.type == "class_definition":
            return self._extract_type_declaration(node, source)

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

            # Also check attribute access
            elif n.type == "attribute":
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
        if parent.type in ("function_definition", "class_definition"):
            # Check if this is the name of the definition
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type in ("identifier", "block", "parameters"):
                    break

        # Variable assignments
        if parent.type == "assignment":
            # Check if this is on the left side
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type == "=":
                    break

        # Parameters
        if parent.type in (
            "parameters",
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
            "identifier",
        ):
            return True

        # Import aliases
        return bool(
            parent.type in {"aliased_import", "dotted_name"}
            and parent.parent
            and parent.parent.type in ("import_statement", "import_from_statement"),
        )

    def _find_definition(
        self,
        name: str,
        _scope_node: Node,
        ast: Node,
        source: bytes,
    ) -> ContextItem | None:
        """Find the definition of a name."""

        # Search for the definition
        def find_definition(node: Node, target_name: str) -> Node | None:
            # Check class definitions
            if node.type in {"class_definition", "function_definition"}:
                for child in node.children:
                    if (
                        child.type == "identifier"
                        and child.text.decode("utf-8") == target_name
                    ):
                        return node

            # Check assignments
            elif node.type == "assignment":
                for child in node.children:
                    if child.type == "=":
                        break
                    if (
                        child.type == "identifier"
                        and child.text.decode("utf-8") == target_name
                    ):
                        return node

            # Recurse through children
            for child in node.children:
                result = find_definition(child, target_name)
                if result:
                    return result

            return None

        def_node = find_definition(ast, name)

        if def_node:
            # Extract the definition
            content = source[def_node.start_byte : def_node.end_byte].decode("utf-8")
            line_number = source[: def_node.start_byte].count(b"\n") + 1

            # Determine the context type
            context_type = ContextType.DEPENDENCY
            if def_node.type == "class_definition":
                context_type = ContextType.TYPE_DEF
                content = self._extract_type_declaration(def_node, source)
            elif def_node.type == "function_definition":
                content = self._extract_scope_declaration(def_node, source)

            return ContextItem(
                type=context_type,
                content=content,
                node=def_node,
                line_number=line_number,
                importance=60,
            )

        return None


class PythonSymbolResolver(BaseSymbolResolver):
    """Python-specific symbol resolution."""

    def __init__(self):
        """Initialize Python symbol resolver."""
        super().__init__("python")

    def _get_node_type_map(self) -> dict[str, str]:
        """Get mapping from AST node types to symbol types."""
        return {
            "function_definition": "function",
            "class_definition": "class",
            "assignment": "variable",
            "typed_parameter": "parameter",
            "default_parameter": "parameter",
            "identifier": "variable",  # In parameter context
            "import_statement": "import",
            "import_from_statement": "import",
        }

    def _is_identifier_node(self, node: Node) -> bool:
        """Check if a node is an identifier."""
        return node.type == "identifier"

    def _is_definition_node(self, node: Node) -> bool:
        """Check if a node defines a symbol."""
        return node.type in (
            "function_definition",
            "class_definition",
            "assignment",
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        )

    def _is_definition_context(self, node: Node) -> bool:
        """Check if an identifier node is in a definition context."""
        # Reuse the implementation from PythonContextExtractor
        extractor = PythonContextExtractor()
        return extractor._is_definition_context(node)

    def _get_defined_name(self, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        if node.type in ("function_definition", "class_definition"):
            # Name is the first identifier child
            for child in node.children:
                if child.type == "identifier":
                    # Would need source bytes to get actual text
                    return None  # Placeholder

        elif node.type == "assignment":
            # Get the left side
            for child in node.children:
                if child.type == "identifier":
                    return None  # Placeholder
                if child.type == "=":
                    break

        elif node.type in (
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        ):
            # First identifier is the parameter name
            for child in node.children:
                if child.type == "identifier":
                    return None  # Placeholder

        return None

    def _creates_new_scope(self, node: Node) -> bool:
        """Check if a node creates a new scope."""
        return node.type in (
            "function_definition",
            "class_definition",
            "lambda",
            "list_comprehension",
            "dictionary_comprehension",
            "set_comprehension",
            "generator_expression",
        )


class PythonScopeAnalyzer(BaseScopeAnalyzer):
    """Python-specific scope analysis."""

    def __init__(self):
        """Initialize Python scope analyzer."""
        super().__init__("python")

    def _get_scope_type_map(self) -> dict[str, str]:
        """Get mapping from AST node types to scope types."""
        return {
            "module": "module",
            "function_definition": "function",
            "class_definition": "class",
            "lambda": "lambda",
            "list_comprehension": "comprehension",
            "dictionary_comprehension": "comprehension",
            "set_comprehension": "comprehension",
            "generator_expression": "generator",
        }

    def _is_scope_node(self, node: Node) -> bool:
        """Check if a node creates a scope."""
        return node.type in self._get_scope_type_map()

    def _is_definition_node(self, node: Node) -> bool:
        """Check if a node defines a symbol."""
        resolver = PythonSymbolResolver()
        return resolver._is_definition_node(node)

    def _is_import_node(self, node: Node) -> bool:
        """Check if a node is an import statement."""
        return node.type in ("import_statement", "import_from_statement")

    def _get_defined_name(self, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        resolver = PythonSymbolResolver()
        return resolver._get_defined_name(node)

    def _extract_imported_names(self, import_node: Node) -> set[str]:
        """Extract symbol names from an import node."""
        names = set()

        if import_node.type == "import_statement":
            # import foo, bar
            for child in import_node.children:
                if child.type == "dotted_name":
                    # Would need source to get the actual name
                    pass
                elif child.type == "aliased_import":
                    # import foo as bar - we want 'bar'
                    for subchild in child.children:
                        if (
                            subchild.type == "identifier"
                            and subchild.prev_sibling
                            and subchild.prev_sibling.type == "as"
                        ):
                            # This is the alias
                            pass

        elif import_node.type == "import_from_statement":
            # from foo import bar, baz
            for child in import_node.children:
                if (
                    child.type == "identifier"
                    and child.prev_sibling
                    and child.prev_sibling.type == "import"
                ):
                    # This is an imported name
                    pass
                elif child.type == "aliased_import":
                    # from foo import bar as baz
                    for subchild in child.children:
                        if (
                            subchild.type == "identifier"
                            and subchild.prev_sibling
                            and subchild.prev_sibling.type == "as"
                        ):
                            # This is the alias
                            pass

        return names


class PythonContextFilter(BaseContextFilter):
    """Python-specific context filtering."""

    def __init__(self):
        """Initialize Python context filter."""
        super().__init__("python")

    def _is_decorator_node(self, node: Node) -> bool:
        """Check if a node is a decorator."""
        return node.type == "decorator"
