"""
Support for Python language.
"""

from __future__ import annotations

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class PythonConfig(LanguageConfig):
    """Language configuration for Python."""

    @property
    def language_id(self) -> str:
        return "python"

    @property
    def chunk_types(self) -> set[str]:
        """Python-specific chunk types."""
        return {
            # Functions and methods
            "function_definition",  # includes async functions
            # Classes
            "class_definition",
            # Decorators (for decorated functions/classes)
            "decorated_definition",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".py", ".pyw", ".pyi"}

    def __init__(self):
        super().__init__()

        # Add rules for more complex scenarios
        self.add_chunk_rule(
            ChunkRule(
                node_types={"lambda"},
                include_children=False,
                priority=5,
                metadata={"type": "lambda_function"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("string")  # Docstrings handled separately

        # TODO: Add more sophisticated rules for:
        # - Nested functions/classes
        # - Comprehensions that might be worth chunking
        # - Import statements grouping

# Register the Python configuration
from .base import language_config_registry
python_config = PythonConfig()
language_config_registry.register(python_config)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

# Plugin implementation for backward compatibility
class PythonPlugin(LanguagePlugin):
    """Plugin for Python language chunking."""

    @property
    def language_name(self) -> str:
        return "python"

    @property
    def supported_extensions(self) -> set[str]:
        return {".py", ".pyi"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "async_function_definition",
            "class_definition",
            "decorated_definition",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Python node."""
        # For function and class definitions, the name is typically
        # the first identifier child after the keyword
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        # Get the name of the current node
        name = self.get_node_name(node, chunk.content.encode("utf-8"))

        if not name:
            return chunk.parent_context

        # Build hierarchical context
        if chunk.parent_context:
            return f"{chunk.parent_context}.{name}"
        return name

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Python nodes with special handling for decorated definitions."""
        # Handle decorated definitions specially
        if node.type == "decorated_definition":
            # The actual function/class is a child of decorated_definition
            for child in node.children:
                if child.type in {
                    "function_definition",
                    "async_function_definition",
                    "class_definition",
                }:
                    # Process the actual definition but use the decorated node's range
                    chunk = self.create_chunk(node, source, file_path, parent_context)
                    if chunk and self.should_include_chunk(chunk):
                        # Update the node type to be more specific
                        chunk.node_type = f"decorated_{child.type}"
                        return chunk
            return None

        # Handle async functions with docstring extraction if configured
        if node.type == "async_function_definition" and self.config.custom_options.get(
            "include_docstrings",
            True,
        ):
            # Check for docstring
            body = None
            for child in node.children:
                if child.type == "block":
                    body = child
                    break

            if body and body.children:
                first_stmt = body.children[0]
                if first_stmt.type == "expression_statement":
                    for subchild in first_stmt.children:
                        if subchild.type == "string":
                            # Has a docstring
                            chunk = self.create_chunk(
                                node,
                                source,
                                file_path,
                                parent_context,
                            )
                            if chunk:
                                chunk.node_type = "async_function_with_docstring"
                                return (
                                    chunk if self.should_include_chunk(chunk) else None
                                )

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
