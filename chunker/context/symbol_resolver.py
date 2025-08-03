"""Base implementation of symbol resolution.

Provides functionality to find symbol definitions and references in the AST.
"""
from tree_sitter import Node

from chunker.interfaces.context import SymbolResolver


class BaseSymbolResolver(SymbolResolver):
    """Base implementation of symbol resolution with common functionality."""

    def __init__(self, language: str):
        """Initialize the symbol resolver.

        Args:
            language: Language identifier
        """
        self.language = language
        self._definition_cache: dict[str, Node | None] = {}
        self._reference_cache: dict[str, list[Node]] = {}

    def find_symbol_definition(self, symbol_name: str, scope_node: Node,
        ast: Node) -> (Node | None):
        """Find where a symbol is defined.

        Args:
            symbol_name: Name of the symbol to find
            scope_node: Node representing the current scope
            ast: Full AST to search

        Returns:
            Node where symbol is defined, or None
        """
        cache_key = f"{symbol_name}:{id(scope_node)}"
        if cache_key in self._definition_cache:
            return self._definition_cache[cache_key]
        current_scope = scope_node
        while current_scope:
            definition = self._search_scope_for_definition(symbol_name,
                current_scope)
            if definition:
                self._definition_cache[cache_key] = definition
                return definition
            current_scope = self._get_parent_scope(current_scope)
        definition = self._search_scope_for_definition(symbol_name, ast)
        self._definition_cache[cache_key] = definition
        return definition

    def get_symbol_type(self, symbol_node: Node) -> str:
        """Get the type of a symbol (function, class, variable, etc).

        Args:
            symbol_node: Node representing the symbol

        Returns:
            Type identifier (e.g., 'function', 'class', 'variable')
        """
        parent = symbol_node.parent
        if not parent:
            return "unknown"
        node_type_map = self._get_node_type_map()
        parent_type = parent.type
        if parent_type in node_type_map:
            return node_type_map[parent_type]
        if parent.parent and parent.parent.type in node_type_map:
            return node_type_map[parent.parent.type]
        if "function" in parent_type or "method" in parent_type:
            return "function"
        if "class" in parent_type:
            return "class"
        if "variable" in parent_type or "assignment" in parent_type:
            return "variable"
        if "parameter" in parent_type:
            return "parameter"
        if "import" in parent_type:
            return "import"
        return "unknown"

    def find_symbol_references(self, symbol_name: str, ast: Node) -> list[Node]:
        """Find all references to a symbol.

        Args:
            symbol_name: Name of the symbol
            ast: AST to search

        Returns:
            List of nodes that reference the symbol
        """
        if symbol_name in self._reference_cache:
            return self._reference_cache[symbol_name]
        references = []

        def find_references(node: Node):
            """Recursively find references to the symbol."""
            if self._is_identifier_node(node):
                name = self._get_node_text(node)
                if name == symbol_name and not self._is_definition_context(node,
                    ):
                    references.append(node)
            for child in node.children:
                find_references(child)
        find_references(ast)
        self._reference_cache[symbol_name] = references
        return references

    def _search_scope_for_definition(self, symbol_name: str, scope_node: Node) -> (
        Node | None):
        """Search within a scope for a symbol definition.

        Args:
            symbol_name: Name to search for
            scope_node: Scope to search within

        Returns:
            Definition node or None
        """

        def search_node(node: Node) -> (Node | None):
            if self._is_definition_node(node):
                defined_name = self._get_defined_name(node)
                if defined_name == symbol_name:
                    return node
            for child in node.children:
                if not self._creates_new_scope(child) or child == scope_node:
                    result = search_node(child)
                    if result:
                        return result
            return None
        return search_node(scope_node)

    def _get_parent_scope(self, node: Node) -> (Node | None):
        """Get the parent scope of a node.

        Args:
            node: Current node

        Returns:
            Parent scope node or None
        """
        current = node.parent
        while current:
            if self._creates_new_scope(current):
                return current
            current = current.parent
        return None

    @staticmethod
    def _get_node_text(_node: Node) -> str:
        """Get the text content of a node.

        Args:
            node: Node to get text from

        Returns:
            Text content
        """
        return ""

    @staticmethod
    def _get_node_type_map() -> dict[str, str]:
        """Get mapping from AST node types to symbol types.

        Returns:
            Dictionary mapping node types to symbol types
        """
        return {}

    @staticmethod
    def _is_identifier_node(node: Node) -> bool:
        """Check if a node is an identifier.

        Args:
            node: Node to check

        Returns:
            True if node is an identifier
        """
        return node.type == "identifier"

    @staticmethod
    def _is_definition_node(_node: Node) -> bool:
        """Check if a node defines a symbol.

        Args:
            node: Node to check

        Returns:
            True if node defines a symbol
        """
        return False

    @staticmethod
    def _is_definition_context(_node: Node) -> bool:
        """Check if an identifier node is in a definition context.

        Args:
            node: Identifier node

        Returns:
            True if this is a definition, not a reference
        """
        return False

    @staticmethod
    def _get_defined_name(_node: Node) -> (str | None):
        """Get the name being defined by a definition node.

        Args:
            node: Definition node

        Returns:
            Name being defined or None
        """
        return None

    @staticmethod
    def _creates_new_scope(_node: Node) -> bool:
        """Check if a node creates a new scope.

        Args:
            node: Node to check

        Returns:
            True if node creates a new scope
        """
        return False
