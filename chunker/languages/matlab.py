"""
Support for MATLAB language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class MATLABConfig(LanguageConfig):
    """Language configuration for MATLAB."""

    @property
    def language_id(self) -> str:
        return "matlab"

    @property
    def chunk_types(self) -> set[str]:
        """MATLAB-specific chunk types."""
        return {
            # Functions
            "function_definition",
            "function_declaration",
            # Classes
            "classdef",
            "class_definition",
            # Methods
            "methods",
            "methods_block",
            "method_definition",
            # Properties
            "properties",
            "properties_block",
            # Events
            "events",
            "events_block",
            # Enumeration
            "enumeration",
            "enumeration_block",
            # Scripts
            "script",
            # Comments
            "comment",
            "block_comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".m", ".mlx"}

    def __init__(self):
        super().__init__()

        # Add rules for nested functions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"nested_function", "local_function"},
                include_children=True,
                priority=5,
                metadata={"type": "nested_function"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("string")
        self.add_ignore_type("number")


# Register the MATLAB configuration

from typing import TYPE_CHECKING

from . import language_config_registry

if TYPE_CHECKING:
    from tree_sitter import Node

language_config_registry.register(MATLABConfig(), aliases=["m", "octave"])


# Plugin implementation for backward compatibility
class MATLABPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for MATLAB language chunking."""

    @property
    def language_name(self) -> str:
        return "matlab"

    @property
    def supported_extensions(self) -> set[str]:
        return {".m", ".mlx"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "function_declaration",
            "classdef",
            "class_definition",
            "methods",
            "methods_block",
            "method_definition",
            "properties",
            "properties_block",
            "events",
            "events_block",
            "enumeration",
            "enumeration_block",
            "script",
            "comment",
            "block_comment",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a MATLAB node."""
        if node.type in {"function_definition", "function_declaration"}:
            # Look for function name after 'function' keyword
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                if child.type == "function_output":
                    # Function with output, name comes after '='
                    for subchild in (
                        child.next_sibling.children if child.next_sibling else []
                    ):
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif node.type in {"classdef", "class_definition"}:
            # Look for class name after 'classdef'
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type == "method_definition":
            # Method name is similar to function
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to MATLAB."""
        chunks = []

        def extract_chunks(n: Node, class_context: str | None = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }

                # Add class context for methods
                if class_context and n.type in {"method_definition", "methods_block"}:
                    chunk["class_context"] = class_context

                chunks.append(chunk)

                # Update class context for children
                if n.type in {"classdef", "class_definition"}:
                    class_context = self.get_node_name(n, source)

            for child in n.children:
                extract_chunks(child, class_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get MATLAB-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # Functions and classes
        if node.type in {
            "function_definition",
            "function_declaration",
            "classdef",
            "class_definition",
        }:
            return True
        # Class components
        if node.type in {
            "methods",
            "methods_block",
            "properties",
            "properties_block",
            "events",
            "events_block",
            "enumeration",
            "enumeration_block",
        }:
            return True
        # Scripts and comments
        return node.type in {"script", "comment", "block_comment"}

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type in {"function_definition", "function_declaration"}:
            if name:
                return f"function {name}"
            return "function"
        if node.type in {"classdef", "class_definition"}:
            if name:
                return f"classdef {name}"
            return "classdef"
        if node.type in {"methods", "methods_block"}:
            return "methods block"
        if node.type in {"properties", "properties_block"}:
            return "properties block"
        if node.type == "method_definition":
            if name:
                return f"method {name}"
            return "method"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process MATLAB nodes with special handling for class structure."""
        # Handle classdef with nested blocks
        if node.type in {"classdef", "class_definition"}:
            # Process the class definition itself
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Set class name as context for children
                class_name = self.get_node_name(node, source)
                if class_name:
                    parent_context = f"class:{class_name}"
                return chunk

        # Handle methods/properties blocks with class context
        if (
            node.type in {"methods", "methods_block", "properties", "properties_block"}
            and parent_context
        ):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Add class information to the chunk
                if parent_context.startswith("class:"):
                    chunk.parent_context = parent_context
                return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        # For classes, pass the class name to children
        if node.type in {"classdef", "class_definition"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"class:{name}"

        # For methods blocks, maintain class context
        if node.type in {"methods", "methods_block"} and chunk.parent_context:
            return chunk.parent_context

        return chunk.node_type
