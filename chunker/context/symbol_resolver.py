"""Base implementation of symbol resolution.

Provides functionality to find symbol definitions and references in the AST.
"""

from tree_sitter import Node

from ..interfaces.context import SymbolResolver


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

    def find_symbol_definition(
        self,
        symbol_name: str,
        scope_node: Node,
        ast: Node,
    ) -> Node | None:
        """Find where a symbol is defined.

        Args:
            symbol_name: Name of the symbol to find
            scope_node: Node representing the current scope
            ast: Full AST to search

        Returns:
            Node where symbol is defined, or None
        """
        # Check cache first
        cache_key = f"{symbol_name}:{id(scope_node)}"
        if cache_key in self._definition_cache:
            return self._definition_cache[cache_key]

        # Search from current scope outward
        current_scope = scope_node

        while current_scope:
            # Search within current scope
            definition = self._search_scope_for_definition(symbol_name, current_scope)
            if definition:
                self._definition_cache[cache_key] = definition
                return definition

            # Move to parent scope
            current_scope = self._get_parent_scope(current_scope)

        # Search at module level if not found in scopes
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
        # Check the parent node to determine symbol type
        parent = symbol_node.parent
        if not parent:
            return "unknown"

        # Map node types to symbol types
        node_type_map = self._get_node_type_map()

        parent_type = parent.type
        if parent_type in node_type_map:
            return node_type_map[parent_type]

        # Check grandparent for more context
        if parent.parent and parent.parent.type in node_type_map:
            return node_type_map[parent.parent.type]

        # Default based on common patterns
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
        # Check cache first
        if symbol_name in self._reference_cache:
            return self._reference_cache[symbol_name]

        references = []

        def find_references(node: Node):
            """Recursively find references to the symbol."""
            # Check if this node is an identifier with the target name
            if self._is_identifier_node(node):
                name = self._get_node_text(node)
                if name == symbol_name:
                    # Verify this is a reference, not a definition
                    if not self._is_definition_context(node):
                        references.append(node)

            # Recurse through children
            for child in node.children:
                find_references(child)

        find_references(ast)

        # Cache and return results
        self._reference_cache[symbol_name] = references
        return references

    # Helper methods

    def _search_scope_for_definition(
        self,
        symbol_name: str,
        scope_node: Node,
    ) -> Node | None:
        """Search within a scope for a symbol definition.

        Args:
            symbol_name: Name to search for
            scope_node: Scope to search within

        Returns:
            Definition node or None
        """

        def search_node(node: Node) -> Node | None:
            # Check if this node defines the symbol
            if self._is_definition_node(node):
                defined_name = self._get_defined_name(node)
                if defined_name == symbol_name:
                    return node

            # Search children, but don't cross scope boundaries
            for child in node.children:
                if not self._creates_new_scope(child) or child == scope_node:
                    result = search_node(child)
                    if result:
                        return result

            return None

        return search_node(scope_node)

    def _get_parent_scope(self, node: Node) -> Node | None:
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

    def _get_node_text(self, node: Node) -> str:
        """Get the text content of a node.

        Args:
            node: Node to get text from

        Returns:
            Text content
        """
        # This would need access to source bytes in real implementation
        # For now, return empty string
        return ""

    # Methods to be overridden by language-specific implementations

    def _get_node_type_map(self) -> dict[str, str]:
        """Get mapping from AST node types to symbol types.

        Returns:
            Dictionary mapping node types to symbol types
        """
        # Override in language-specific implementations
        return {}

    def _is_identifier_node(self, node: Node) -> bool:
        """Check if a node is an identifier.

        Args:
            node: Node to check

        Returns:
            True if node is an identifier
        """
        # Override in language-specific implementations
        return node.type == "identifier"

    def _is_definition_node(self, node: Node) -> bool:
        """Check if a node defines a symbol.

        Args:
            node: Node to check

        Returns:
            True if node defines a symbol
        """
        # Override in language-specific implementations
        return False

    def _is_definition_context(self, node: Node) -> bool:
        """Check if an identifier node is in a definition context.

        Args:
            node: Identifier node

        Returns:
            True if this is a definition, not a reference
        """
        # Override in language-specific implementations
        return False

    def _get_defined_name(self, node: Node) -> str | None:
        """Get the name being defined by a definition node.

        Args:
            node: Definition node

        Returns:
            Name being defined or None
        """
        # Override in language-specific implementations
        return None

    def _creates_new_scope(self, node: Node) -> bool:
        """Check if a node creates a new scope.

        Args:
            node: Node to check

        Returns:
            True if node creates a new scope
        """
        # Override in language-specific implementations
        return False
