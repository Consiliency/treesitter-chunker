from __future__ import annotations

from typing import TYPE_CHECKING

from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class CSharpPlugin(LanguagePlugin):
    """Plugin for C# language chunking using tree-sitter-c-sharp node types."""

    @property
    def language_name(self) -> str:
        return "c_sharp"

    @property
    def supported_extensions(self) -> set[str]:
        return {".cs", ".csx"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "class_declaration",
            "struct_declaration",
            "interface_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
            "property_declaration",
            "field_declaration",
            "record_declaration",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None
