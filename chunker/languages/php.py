"""
Support for PHP language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class PHPConfig(LanguageConfig):
    """Language configuration for PHP."""

    @property
    def language_id(self) -> str:
        return "php"

    @property
    def chunk_types(self) -> set[str]:
        """PHP-specific chunk types."""
        return {
            "class_declaration",
            "interface_declaration",
            "trait_declaration",
            "enum_declaration",
            "function_definition",
            "method_declaration",
            "property_declaration",
            "const_declaration",
            "namespace_definition",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".php", ".php3", ".php4", ".php5", ".phtml"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"anonymous_function_creation_expression"},
                include_children=True,
                priority=5,
                metadata={"type": "closure"},
            ),
        )
        # Do not ignore comments globally; tests expect some mixed-content chunks
        self.add_ignore_type("string")
        self.add_ignore_type("integer")


class PHPPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for PHP language chunking."""

    @property
    def language_name(self) -> str:
        return "php"

    @property
    def supported_extensions(self) -> set[str]:
        return {".php", ".php3", ".php4", ".php5", ".phtml"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "class_declaration",
            "interface_declaration",
            "trait_declaration",
            "function_definition",
            "method_declaration",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a PHP node."""
        # Look for name or identifier in children
        for child in node.children:
            if child.type == "name":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to PHP."""
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

                # Add PHP-specific metadata
                if n.type in {"method_declaration", "function_definition"}:
                    chunk["is_function"] = True
                    if "private" in content[:50]:
                        chunk["visibility"] = "private"
                    elif "protected" in content[:50]:
                        chunk["visibility"] = "protected"
                    elif "public" in content[:50]:
                        chunk["visibility"] = "public"
                    else:
                        chunk["visibility"] = "public"  # PHP default for functions

                elif n.type == "trait_declaration":
                    chunk["is_trait"] = True
                elif n.type == "interface_declaration":
                    chunk["is_interface"] = True
                elif n.type == "enum_declaration":
                    chunk["is_enum"] = True
                elif n.type == "class_declaration":
                    chunk["is_class"] = True
                    # Check for abstract or final
                    if "abstract" in content[:100]:
                        chunk["is_abstract"] = True
                    if "final" in content[:100]:
                        chunk["is_final"] = True

                chunks.append(chunk)

            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get PHP-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        return node.type in {
            "class_declaration",
            "interface_declaration",
            "trait_declaration",
            "function_definition",
            "method_declaration",
        }

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        node_context_map = {
            "class_declaration": ("class", "class"),
            "interface_declaration": ("interface", "interface"),
            "trait_declaration": ("trait", "trait"),
            "enum_declaration": ("enum", "enum"),
            "function_definition": ("function", "function"),
            "method_declaration": ("function", "method"),
            "property_declaration": ("property", "property"),
            "const_declaration": ("const", "constant"),
            "namespace_definition": ("namespace", "namespace"),
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
        """Process PHP nodes with special handling for methods and properties."""
        if node.type == "method_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                content = source[node.start_byte : node.end_byte].decode("utf-8")
                if "static" in content[:100]:
                    chunk.metadata = {"is_static": True}
                return chunk

        return super().process_node(node, source, file_path, parent_context)


# Register the PHP configuration
from .base import language_config_registry

language_config_registry.register(PHPConfig())
