"""Base implementation of context extraction.

Provides a foundation for language-specific context extractors with
common AST traversal and extraction logic.
"""
from typing import Any

from tree_sitter import Node

from chunker.interfaces.context import ContextExtractor, ContextItem, ContextType


class BaseContextExtractor(ContextExtractor):
    """Base implementation of context extraction with common functionality."""

    def __init__(self, language: str):
        """Initialize the context extractor.

        Args:
            language: Language identifier (e.g., 'python', 'javascript')
        """
        self.language = language
        self._context_cache: dict[int, list[ContextItem]] = {}

    def extract_imports(self, ast: Node, source: bytes) -> list[ContextItem]:
        """Extract all import statements from the AST.

        Args:
            ast: Root node of the AST
            source: Original source code

        Returns:
            List of import context items
        """
        imports = []

        def visit_imports(node: Node, depth: int = 0):
            if self._is_import_node(node):
                content = source[node.start_byte:node.end_byte].decode("utf-8")
                start_line = source[:node.start_byte].count(b"\n") + 1
                imports.append(ContextItem(type=ContextType.IMPORT, content=content, node=node, line_number=start_line, importance=90),
                    )
            for child in node.children:
                visit_imports(child, depth + 1)
        visit_imports(ast)
        return sorted(imports)

    def extract_type_definitions(self, ast: Node, source: bytes) -> list[ContextItem]:
        """Extract type definitions (classes, interfaces, types).

        Args:
            ast: Root node of the AST
            source: Original source code

        Returns:
            List of type definition context items
        """
        type_defs = []

        def visit_types(node: Node, depth: int = 0):
            if self._is_type_definition_node(node):
                declaration = self._extract_type_declaration(node, source)
                if declaration:
                    start_line = source[:node.start_byte].count(b"\n") + 1
                    type_defs.append(ContextItem(type=ContextType.TYPE_DEF,
                        content=declaration, node=node, line_number=start_line, importance=80))
            for child in node.children:
                visit_types(child, depth + 1)
        visit_types(ast)
        return sorted(type_defs)

    def extract_dependencies(self, node: Node, ast: Node, source: bytes,
        ) -> list[ContextItem]:
        """Extract dependencies for a specific node.

        Args:
            node: Node to analyze dependencies for
            ast: Full AST for context
            source: Original source code

        Returns:
            List of dependency context items
        """
        dependencies = []
        references = self._find_references_in_node(node, source)
        for ref_name, _ref_node in references:
            definition = self._find_definition(ref_name, node, ast, source)
            if definition:
                dependencies.append(definition)
        seen = set()
        unique_deps = []
        for dep in dependencies:
            dep_id = dep.type, dep.content
            if dep_id not in seen:
                seen.add(dep_id)
                unique_deps.append(dep)
        return sorted(unique_deps)

    def extract_parent_context(self, node: Node, _ast: Node, source: bytes,
        ) -> list[ContextItem]:
        """Extract parent scope context (enclosing class, function, etc).

        Args:
            node: Node to get parent context for
            ast: Full AST
            source: Original source code

        Returns:
            List of parent context items
        """
        parent_contexts = []
        current = node.parent
        while current:
            if self._is_scope_node(current):
                declaration = self._extract_scope_declaration(current, source)
                if declaration:
                    start_line = source[:current.start_byte].count(b"\n") + 1
                    parent_contexts.append(ContextItem(type=ContextType.
                        PARENT_SCOPE, content=declaration, node=current,
                        line_number=start_line, importance=70))
            current = current.parent
        parent_contexts.reverse()
        return parent_contexts

    def find_decorators(self, node: Node, source: bytes) -> list[ContextItem]:
        """Extract decorators for a node (if applicable).

        Args:
            node: Node to check for decorators
            source: Original source code

        Returns:
            List of decorator context items
        """
        decorators = []
        if node.parent:
            for i, sibling in enumerate(node.parent.children):
                if sibling == node:
                    for j in range(i - 1, -1, -1):
                        prev_sibling = node.parent.children[j]
                        if self._is_decorator_node(prev_sibling):
                            content = source[prev_sibling.start_byte:
                                prev_sibling.end_byte].decode("utf-8")
                            start_line = source[:prev_sibling.start_byte
                                ].count(b"\n") + 1
                            decorators.append(ContextItem(type=ContextType.
                                DECORATOR, content=content, node=prev_sibling, line_number=start_line,
                                importance=60))
                        else:
                            break
                    break
        decorators.reverse()
        return decorators

    @staticmethod
    def build_context_prefix(context_items: list[ContextItem], max_size: (
        int | None) = None) -> str:
        """Build a context string to prepend to a chunk.

        Args:
            context_items: List of context items to include
            max_size: Maximum size in characters (None for no limit)

        Returns:
            Formatted context string
        """
        if not context_items:
            return ""
        sorted_items = sorted(context_items)
        grouped: dict[ContextType, list[ContextItem]] = {}
        for item in sorted_items:
            if item.type not in grouped:
                grouped[item.type] = []
            grouped[item.type].append(item)
        lines = []
        if ContextType.IMPORT in grouped:
            lines.extend(item.content for item in grouped[ContextType.IMPORT])
            lines.append("")
        if ContextType.TYPE_DEF in grouped:
            lines.extend(item.content for item in grouped[ContextType.TYPE_DEF]
                )
            lines.append("")
        for context_type in [ContextType.DECORATOR, ContextType.
            PARENT_SCOPE, ContextType.DEPENDENCY, ContextType.NAMESPACE,
            ContextType.CONSTANT, ContextType.GLOBAL_VAR]:
            if context_type in grouped:
                lines.extend(item.content for item in grouped[context_type])
        context_str = "\n".join(lines).strip()
        if max_size and len(context_str) > max_size:
            context_str = context_str[:max_size].rsplit("\n", 1)[0]
            context_str += "\n# ... (context truncated)"
        return context_str

    @staticmethod
    def _is_import_node(_node: Node) -> bool:
        """Check if a node represents an import statement.

        Args:
            node: Node to check

        Returns:
            True if node is an import
        """
        return False

    @staticmethod
    def _is_type_definition_node(_node: Node) -> bool:
        """Check if a node represents a type definition.

        Args:
            node: Node to check

        Returns:
            True if node is a type definition
        """
        return False

    @staticmethod
    def _is_scope_node(_node: Node) -> bool:
        """Check if a node represents a scope (function, class, etc).

        Args:
            node: Node to check

        Returns:
            True if node creates a new scope
        """
        return False

    @staticmethod
    def _is_decorator_node(_node: Node) -> bool:
        """Check if a node represents a decorator.

        Args:
            node: Node to check

        Returns:
            True if node is a decorator
        """
        return False

    @staticmethod
    def _extract_type_declaration(_node: Node, _source: bytes) -> (str | None):
        """Extract just the declaration part of a type definition.

        Args:
            node: Type definition node
            source: Source code

        Returns:
            Declaration string or None
        """
        return None

    @staticmethod
    def _extract_scope_declaration(_node: Node, _source: bytes) -> (str | None):
        """Extract just the declaration part of a scope.

        Args:
            node: Scope node
            source: Source code

        Returns:
            Declaration string or None
        """
        return None

    @staticmethod
    def _find_references_in_node(_node: Node, _source: bytes) -> list[tuple[
        str, Node]]:
        """Find all identifier references in a node.

        Args:
            node: Node to search in
            source: Source code

        Returns:
            List of (identifier_name, node) tuples
        """
        return []

    @staticmethod
    def _find_definition(_name: str, _scope_node: Node, _ast: Node, _source:
        bytes) -> (ContextItem | None):
        """Find the definition of a name.

        Args:
            name: Name to find
            scope_node: Current scope
            ast: Full AST
            source: Source code

        Returns:
            ContextItem for the definition or None
        """
        return None

    @staticmethod
    def process_node(node: Node, context: dict[str, Any]) -> Any:
        """Process a single AST node.

        Args:
            node: The AST node to process
            context: Processing context

        Returns:
            Processing result
        """
        return None

    @staticmethod
    def should_process_children(_node: Node, _context: dict[str, Any]) -> bool:
        """Determine if children of this node should be processed.

        Args:
            node: The current AST node
            context: Processing context

        Returns:
            True if children should be processed
        """
        return True
