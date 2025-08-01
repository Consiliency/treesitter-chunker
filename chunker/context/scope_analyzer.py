"""Base implementation of scope analysis.

Provides functionality to analyze scope relationships and visible symbols.
"""
from tree_sitter import Node

from chunker.interfaces.context import ScopeAnalyzer


class BaseScopeAnalyzer(ScopeAnalyzer):
    """Base implementation of scope analysis with common functionality."""

    def __init__(self, language: str):
        """Initialize the scope analyzer.

        Args:
            language: Language identifier
        """
        self.language = language
        self._scope_cache: dict[int, Node | None] = {}
        self._visible_symbols_cache: dict[int, set[str]] = {}

    def get_enclosing_scope(self, node: Node) -> (Node | None):
        """Get the enclosing scope for a node.

        Args:
            node: Node to analyze

        Returns:
            Enclosing scope node (function, class, etc) or None
        """
        node_id = id(node)
        if node_id in self._scope_cache:
            return self._scope_cache[node_id]
        current = node.parent
        while current:
            if self._is_scope_node(current):
                self._scope_cache[node_id] = current
                return current
            current = current.parent
        self._scope_cache[node_id] = None
        return None

    def get_scope_type(self, scope_node: Node) -> str:
        """Get the type of a scope.

        Args:
            scope_node: Scope node

        Returns:
            Scope type (e.g., 'function', 'class', 'module')
        """
        node_type = scope_node.type
        scope_type_map = self._get_scope_type_map()
        if node_type in scope_type_map:
            return scope_type_map[node_type]
        if "function" in node_type or "method" in node_type:
            return "function"
        if "class" in node_type:
            return "class"
        if "module" in node_type or node_type == "source_file":
            return "module"
        if "block" in node_type:
            return "block"
        return "unknown"

    def get_visible_symbols(self, scope_node: Node, ast: Node) -> set[str]:
        """Get all symbols visible from a scope.

        Args:
            scope_node: Node representing the scope
            ast: Full AST for context

        Returns:
            Set of visible symbol names
        """
        scope_id = id(scope_node)
        if scope_id in self._visible_symbols_cache:
            return self._visible_symbols_cache[scope_id]
        visible = set()
        local_symbols = self._get_local_symbols(scope_node)
        visible.update(local_symbols)
        parent_scope = self.get_enclosing_scope(scope_node)
        while parent_scope:
            parent_symbols = self._get_local_symbols(parent_scope)
            visible.update(parent_symbols)
            parent_scope = self.get_enclosing_scope(parent_scope)
        if scope_node != ast:
            module_symbols = self._get_local_symbols(ast)
            visible.update(module_symbols)
        imported_symbols = self._get_imported_symbols(ast)
        visible.update(imported_symbols)
        self._visible_symbols_cache[scope_id] = visible
        return visible

    def get_scope_chain(self, node: Node) -> list[Node]:
        """Get the chain of enclosing scopes.

        Args:
            node: Starting node

        Returns:
            List of scope nodes from innermost to outermost
        """
        scopes = []
        if self._is_scope_node(node):
            scopes.append(node)
        current = self.get_enclosing_scope(node)
        while current:
            scopes.append(current)
            current = self.get_enclosing_scope(current)
        return scopes

    def _get_local_symbols(self, scope_node: Node) -> set[str]:
        """Get symbols defined directly in a scope.

        Args:
            scope_node: Scope to analyze

        Returns:
            Set of symbol names defined in the scope
        """
        symbols = set()

        def collect_definitions(node: Node, depth: int = 0):
            """Recursively collect symbol definitions."""
            if depth > 0 and self._is_scope_node(node):
                return
            if self._is_definition_node(node):
                name = self._get_defined_name(node)
                if name:
                    symbols.add(name)
            for child in node.children:
                collect_definitions(child, depth + 1)
        collect_definitions(scope_node)
        return symbols

    def _get_imported_symbols(self, ast: Node) -> set[str]:
        """Get symbols that are imported.

        Args:
            ast: Full AST

        Returns:
            Set of imported symbol names
        """
        imports = set()

        def collect_imports(node: Node):
            """Recursively collect imported symbols."""
            if self._is_import_node(node):
                imported_names = self._extract_imported_names(node)
                imports.update(imported_names)
            for child in node.children:
                collect_imports(child)
        collect_imports(ast)
        return imports

    @staticmethod
    def _get_scope_type_map() -> dict[str, str]:
        """Get mapping from AST node types to scope types.

        Returns:
            Dictionary mapping node types to scope types
        """
        return {"module": "module", "source_file": "module",
            "function_definition": "function", "class_definition": "class"}

    @staticmethod
    def _is_scope_node(_node: Node) -> bool:
        """Check if a node creates a scope.

        Args:
            node: Node to check

        Returns:
            True if node creates a scope
        """
        return False

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
    def _is_import_node(_node: Node) -> bool:
        """Check if a node is an import statement.

        Args:
            node: Node to check

        Returns:
            True if node is an import
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
    def _extract_imported_names(_import_node: Node) -> set[str]:
        """Extract symbol names from an import node.

        Args:
            import_node: Import statement node

        Returns:
            Set of imported symbol names
        """
        return set()
