"""
Support for MATLAB language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class MATLABConfig(LanguageConfig):
    """Language configuration for MATLAB."""

    @property
    def language_id(self) -> str:
        return "matlab"

    @property
    def chunk_types(self) -> set[str]:
        """MATLAB-specific chunk types."""
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

    @property
    def file_extensions(self) -> set[str]:
        return {".m", ".mlx"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"nested_function", "local_function"},
                include_children=True,
                priority=5,
                metadata={"type": "nested_function"},
            ),
        )
        self.add_ignore_type("string")
        self.add_ignore_type("number")


# Register the MATLAB configuration


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

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a MATLAB node."""
        if node.type in {"function_definition", "function_declaration"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                if child.type == "function_output":
                    for subchild in (
                        child.next_sibling.children if child.next_sibling else []
                    ):
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif (
            node.type in {"classdef", "class_definition"}
            or node.type == "method_definition"
        ):
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
                if class_context and n.type in {"method_definition", "methods_block"}:
                    chunk["class_context"] = class_context
                chunks.append(chunk)
                if n.type in {"classdef", "class_definition"}:
                    class_context = self.get_node_name(n, source)
            for child in n.children:
                extract_chunks(child, class_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get MATLAB-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in {
            "function_definition",
            "function_declaration",
            "classdef",
            "class_definition",
        }:
            return True
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
        return node.type in {"script", "comment", "block_comment"}

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format (prefix, default, needs_name)
        node_context_map = {
            "function_definition": ("function", "function", True),
            "function_declaration": ("function", "function", True),
            "classdef": ("classdef", "classdef", True),
            "class_definition": ("classdef", "classdef", True),
            "methods": (None, "methods block", False),
            "methods_block": (None, "methods block", False),
            "properties": (None, "properties block", False),
            "properties_block": (None, "properties block", False),
            "method_definition": ("method", "method", True),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        prefix, default, needs_name = context_info
        if not needs_name or prefix is None:
            return default

        name = self.get_node_name(node, source)
        return f"{prefix} {name}" if name else default

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process MATLAB nodes with special handling for class structure."""
        if node.type in {"classdef", "class_definition"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                class_name = self.get_node_name(node, source)
                if class_name:
                    parent_context = f"class:{class_name}"
                return chunk
        if (
            node.type in {"methods", "methods_block", "properties", "properties_block"}
            and parent_context
        ):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                if parent_context.startswith("class:"):
                    chunk.parent_context = parent_context
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        if node.type in {"classdef", "class_definition"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"class:{name}"
        if node.type in {"methods", "methods_block"} and chunk.parent_context:
            return chunk.parent_context
        return chunk.node_type
