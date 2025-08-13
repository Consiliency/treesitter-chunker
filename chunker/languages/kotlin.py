"""
Support for Kotlin language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class KotlinConfig(LanguageConfig):
    """Language configuration for Kotlin."""

    @property
    def language_id(self) -> str:
        return "kotlin"

    @property
    def chunk_types(self) -> set[str]:
        """Kotlin-specific chunk types."""
        return {
            "class_declaration",
            "object_declaration",
            "interface_declaration",
            "function_declaration",
            "property_declaration",
            "enum_class_declaration",
            "sealed_class_declaration",
            "data_class_declaration",
            "companion_object",
            "init_block",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".kt", ".kts", ".ktm"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"lambda_literal"},
                include_children=True,
                priority=5,
                metadata={"type": "lambda"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("string_literal")
        self.add_ignore_type("integer_literal")


class KotlinPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Kotlin language chunking."""

    @property
    def language_name(self) -> str:
        return "kotlin"

    @property
    def supported_extensions(self) -> set[str]:
        return {".kt", ".kts", ".ktm"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "class_declaration",
            "object_declaration",
            "interface_declaration",
            "function_declaration",
            "property_declaration",
            "enum_class_declaration",
            "sealed_class_declaration",
            "data_class_declaration",
            "companion_object",
            "init_block",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Kotlin node."""
        # Look for identifier in children
        for child in node.children:
            if child.type == "type_identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Kotlin."""
        chunks = []

        def extract_chunks(n: Node, _parent_type: str | None = None):
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

                # Add Kotlin-specific metadata
                if n.type == "function_declaration":
                    chunk["is_function"] = True
                    if "private" in content[:50]:
                        chunk["visibility"] = "private"
                    elif "protected" in content[:50]:
                        chunk["visibility"] = "protected"
                    elif "public" in content[:50]:
                        chunk["visibility"] = "public"
                    elif "internal" in content[:50]:
                        chunk["visibility"] = "internal"
                    else:
                        chunk["visibility"] = "public"  # Kotlin default

                    if "suspend" in content[:50]:
                        chunk["is_suspend"] = True
                    if "inline" in content[:50]:
                        chunk["is_inline"] = True

                elif n.type == "class_declaration":
                    # Check for class modifiers
                    if "data" in content[:50]:
                        chunk["is_data_class"] = True
                    if "sealed" in content[:50]:
                        chunk["is_sealed"] = True
                    if "abstract" in content[:50]:
                        chunk["is_abstract"] = True
                    if "open" in content[:50]:
                        chunk["is_open"] = True

                elif n.type == "object_declaration":
                    chunk["is_object"] = True
                elif n.type == "interface_declaration":
                    chunk["is_interface"] = True
                elif n.type == "property_declaration":
                    chunk["is_property"] = True
                    if "val" in content[:50]:
                        chunk["is_immutable"] = True
                    elif "var" in content[:50]:
                        chunk["is_mutable"] = True

                chunks.append(chunk)

            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Kotlin-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        return node.type in {
            "class_declaration",
            "object_declaration",
            "interface_declaration",
            "function_declaration",
            "property_declaration",
            "enum_class_declaration",
            "sealed_class_declaration",
            "data_class_declaration",
            "companion_object",
            "init_block",
        }

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        node_context_map = {
            "class_declaration": ("class", "class"),
            "object_declaration": ("object", "object"),
            "interface_declaration": ("interface", "interface"),
            "function_declaration": ("fun", "function"),
            "property_declaration": ("property", "property"),
            "enum_class_declaration": ("enum class", "enum"),
            "sealed_class_declaration": ("sealed class", "sealed class"),
            "data_class_declaration": ("data class", "data class"),
            "companion_object": ("companion object", "companion object"),
            "init_block": ("init", "init block"),
        }

        if node.type not in node_context_map:
            return None

        prefix, default = node_context_map[node.type]
        name = self.get_node_name(node, source)
        return f"{prefix} {name}" if name else default

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Kotlin nodes with special handling for companion objects and extensions."""
        if node.type == "companion_object":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.node_type = "companion_object"
                return chunk

        return super().process_node(node, source, file_path, parent_context)


# Register the Kotlin configuration
from .base import language_config_registry

language_config_registry.register(KotlinConfig())
