"""
Support for Zig language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class ZigConfig(LanguageConfig):
    """Language configuration for Zig."""

    @property
    def language_id(self) -> str:
        return "zig"

    @property
    def chunk_types(self) -> set[str]:
        """Zig-specific chunk types."""
        return {
            "function_declaration",
            "struct_declaration",
            "enum_declaration",
            "union_declaration",
            "test_declaration",
            "comptime_declaration",
            "const_declaration",
            "var_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".zig"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"error_set_declaration"},
                include_children=False,
                priority=5,
                metadata={"type": "error_set"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"asm_expression"},
                include_children=True,
                priority=4,
                metadata={"type": "inline_assembly"},
            ),
        )
        self.add_ignore_type("line_comment")
        self.add_ignore_type("container_doc_comment")


# Register the Zig configuration


class ZigPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Zig language chunking."""

    @property
    def language_name(self) -> str:
        return "zig"

    @property
    def supported_extensions(self) -> set[str]:
        return {".zig"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "struct_declaration",
            "enum_declaration",
            "union_declaration",
            "test_declaration",
            "comptime_declaration",
            "error_set_declaration",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Zig node."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if node.type == "test_declaration" and child.type == "string_literal":
                test_name = source[child.start_byte : child.end_byte].decode("utf-8")
                return test_name.strip('"')
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Zig."""
        chunks = []

        def extract_chunks(n: Node, container_name: str | None = None):
            if n.type == "function_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "function",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                for child in n.children:
                    if child.type == "pub" or (
                        child.type == "visibility_modifier"
                        and source[child.start_byte : child.end_byte] == b"pub"
                    ):
                        chunk["visibility"] = "public"
                        break
                else:
                    chunk["visibility"] = "private"
                if container_name:
                    chunk["container"] = container_name
                chunks.append(chunk)
            elif n.type == "struct_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "struct",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                chunks.append(chunk)
                for child in n.children:
                    extract_chunks(child, name)
            elif n.type == "enum_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "enum",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "test_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "test",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "union_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "union",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                chunks.append(chunk)
                for child in n.children:
                    extract_chunks(child, name)
            elif n.type == "error_set_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "error_set",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "comptime_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "comptime",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            else:
                for child in n.children:
                    extract_chunks(child, container_name)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Zig-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type == "asm_expression":
            return True
        if node.type in {"const_declaration", "var_declaration"}:
            for child in node.children:
                if child.type in {
                    "function_expression",
                    "struct_expression",
                    "anonymous_struct",
                }:
                    return True
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Handle function declarations specially for visibility
        if node.type == "function_declaration":
            return self._get_function_context(node, source)

        # Map other node types
        node_context_map = {
            "struct_declaration": ("struct", "struct"),
            "enum_declaration": ("enum", "enum"),
            "union_declaration": ("union", "union"),
            "test_declaration": ('test "', '"', "test"),
            "error_set_declaration": ("error", "error"),
            "comptime_declaration": ("comptime", "comptime"),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        name = self.get_node_name(node, source)
        if len(context_info) == 3:  # test_declaration case
            prefix, suffix, default = context_info
            return f"{prefix}{name}{suffix}" if name else default
        prefix, default = context_info
        return f"{prefix} {name}" if name else default

    def _get_function_context(self, node: Node, source: bytes) -> str:
        """Get function context with visibility."""
        is_public = any(
            child.type == "pub"
            or (
                child.type == "visibility_modifier"
                and source[child.start_byte : child.end_byte] == b"pub"
            )
            for child in node.children
        )
        visibility = "pub " if is_public else ""
        name = self.get_node_name(node, source)
        return f"{visibility}fn {name}" if name else f"{visibility}fn"

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Zig nodes with special handling for visibility and tests."""
        if node.type == "function_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                for child in node.children:
                    if child.type == "pub" or (
                        child.type == "visibility_modifier"
                        and source[child.start_byte : child.end_byte] == b"pub"
                    ):
                        chunk.metadata = {"visibility": "public"}
                        break
                else:
                    chunk.metadata = {"visibility": "private"}
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "test_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "test"
                test_name = self.get_node_name(node, source)
                if test_name:
                    chunk.metadata = {"test_name": test_name}
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "asm_expression":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "inline_assembly"
                return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)
