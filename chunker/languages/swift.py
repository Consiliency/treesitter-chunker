"""
Support for Swift language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class SwiftConfig(LanguageConfig):
    """Language configuration for Swift."""

    @property
    def language_id(self) -> str:
        return "swift"

    @property
    def chunk_types(self) -> set[str]:
        """Swift-specific chunk types."""
        return {
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
            "protocol_declaration",
            "extension_declaration",
            "function_declaration",
            "init_declaration",
            "deinit_declaration",
            "subscript_declaration",
            "property_declaration",
            "actor_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".swift"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"computed_property"},
                include_children=True,
                priority=5,
                metadata={"type": "computed_property"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("string_literal")
        self.add_ignore_type("integer_literal")


class SwiftPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Swift language chunking."""

    @property
    def language_name(self) -> str:
        return "swift"

    @property
    def supported_extensions(self) -> set[str]:
        return {".swift"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
            "protocol_declaration",
            "extension_declaration",
            "function_declaration",
            "init_declaration",
            "deinit_declaration",
            "subscript_declaration",
            "property_declaration",
            "actor_declaration",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Swift node."""
        # Look for identifier in children
        for child in node.children:
            if child.type == "type_identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Swift."""
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

                # Add Swift-specific metadata
                if n.type in {"function_declaration", "init_declaration"}:
                    chunk["is_method"] = True
                    if "private" in content[:50]:
                        chunk["visibility"] = "private"
                    elif "internal" in content[:50]:
                        chunk["visibility"] = "internal"
                    elif "public" in content[:50]:
                        chunk["visibility"] = "public"
                    else:
                        chunk["visibility"] = "internal"  # Swift default

                elif n.type == "actor_declaration":
                    chunk["is_actor"] = True
                elif n.type == "protocol_declaration":
                    chunk["is_protocol"] = True
                elif n.type in {"struct_declaration"}:
                    chunk["is_value_type"] = True
                elif n.type == "class_declaration":
                    chunk["is_reference_type"] = True

                chunks.append(chunk)

            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Swift-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        return node.type in {
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
            "protocol_declaration",
            "extension_declaration",
            "function_declaration",
            "init_declaration",
            "deinit_declaration",
            "subscript_declaration",
            "property_declaration",
            "actor_declaration",
        }

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        node_context_map = {
            "class_declaration": ("class", "class"),
            "struct_declaration": ("struct", "struct"),
            "enum_declaration": ("enum", "enum"),
            "protocol_declaration": ("protocol", "protocol"),
            "extension_declaration": ("extension", "extension"),
            "function_declaration": ("func", "function"),
            "init_declaration": ("init", "initializer"),
            "deinit_declaration": ("deinit", "deinitializer"),
            "subscript_declaration": ("subscript", "subscript"),
            "property_declaration": ("var/let", "property"),
            "actor_declaration": ("actor", "actor"),
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
        """Process Swift nodes with special handling for complex constructs."""
        if node.type == "extension_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.node_type = "extension"
                return chunk

        return super().process_node(node, source, file_path, parent_context)


# Register the Swift configuration
from .base import language_config_registry

language_config_registry.register(SwiftConfig())
