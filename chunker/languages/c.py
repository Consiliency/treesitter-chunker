from __future__ import annotations

from .base import LanguageConfig
from .plugin_base import LanguagePlugin


class CConfig(LanguageConfig):
    """Language configuration for C."""

    @property
    def language_id(self) -> str:
        return "c"

    @property
    def chunk_types(self) -> set[str]:
        """C-specific chunk types."""
        return {"function_definition", "struct_specifier",
            "union_specifier", "enum_specifier", "type_definition"}

    @property
    def file_extensions(self) -> set[str]:
        return {".c", ".h"}

<<<<<<< HEAD

# Register the C configuration
from .base import language_config_registry

language_config_registry.register(CConfig())
=======
>>>>>>> origin/main

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

    from chunker.types import CodeChunk


class CPlugin(LanguagePlugin):
    """Plugin for C language chunking."""

    @property
    def language_name(self) -> str:
        return "c"

    @property
    def supported_extensions(self) -> set[str]:
        return {".c", ".h"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {"function_definition", "struct_specifier",
            "union_specifier", "enum_specifier", "type_definition"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract name from C nodes."""
        if node.type == "function_definition":
            for child in node.children:
                if child.type == "function_declarator":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[subchild.start_byte:subchild.end_byte
                                ].decode("utf-8")
        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                return source[child.start_byte:child.end_byte].decode("utf-8")
        return None

    def get_context_for_children(self, node: Node, chunk: CodeChunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode())
        if name:
            if node.type == "struct_specifier":
                return f"struct {name}"
            if node.type == "union_specifier":
                return f"union {name}"
            if node.type == "enum_specifier":
                return f"enum {name}"
            if node.type == "function_definition":
                return f"function {name}"
        return node.type
