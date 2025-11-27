from __future__ import annotations

from chunker.utils.text import safe_decode_bytes

from .base import LanguageConfig
from .plugin_base import LanguagePlugin


class JavaScriptConfig(LanguageConfig):
    """Language configuration for JavaScript."""

    @property
    def language_id(self) -> str:
        return "javascript"

    @property
    def chunk_types(self) -> set[str]:
        """JavaScript-specific chunk types."""
        return {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "import_statement",
            "variable_declarator",
            # Add namespace-like and enum patterns via TS superset nodes where present
            "namespace_export",
            "enum_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".js", ".jsx", ".mjs", ".cjs"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("comment")
        self.add_ignore_type("template_string")


# Register the JavaScript configuration
from .base import language_config_registry

javascript_config = JavaScriptConfig()
language_config_registry.register(javascript_config)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

    from chunker.types import CodeChunk


class JavaScriptPlugin(LanguagePlugin):
    """Plugin for JavaScript/TypeScript language chunking."""

    @property
    def language_name(self) -> str:
        return "javascript"

    @property
    def supported_extensions(self) -> set[str]:
        return {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "variable_declarator",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract name from JavaScript nodes."""
        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                return safe_decode_bytes(source[child.start_byte : child.end_byte])
        if node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        if node.type == "variable_declarator":
            for child in node.children:
                if child.type == "identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode())
        if name:
            if node.type == "class_declaration":
                return f"class {name}"
            if node.type in {
                "function_declaration",
                "function_expression",
                "arrow_function",
            }:
                return f"function {name}"
            if node.type == "method_definition":
                return f"method {name}"
        return node.type

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """Process JavaScript nodes with special handling."""
        if node.type == "variable_declarator":
            has_function = False
            for child in node.children:
                if child.type in {"arrow_function", "function_expression"}:
                    has_function = True
                    break
            if not has_function:
                return None
        if node.type == "export_statement":
            for child in node.children:
                if child.type in self.chunk_node_types:
                    return self.process_node(child, source, file_path, parent_context)
        return super().process_node(node, source, file_path, parent_context)
