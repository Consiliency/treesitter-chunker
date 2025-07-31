"""
Support for Zig language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class ZigConfig(LanguageConfig):
    """Language configuration for Zig."""

    @property
    def language_id(self) -> str:
        return "zig"

    @property
    def chunk_types(self) -> set[str]:
        """Zig-specific chunk types."""
        return {
            # Functions
            "function_declaration",
            # Structs and types
            "struct_declaration",
            "enum_declaration",
            "union_declaration",
            # Tests
            "test_declaration",
            # Other declarations
            "comptime_declaration",
            "const_declaration",
            "var_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".zig"}

    def __init__(self):
        super().__init__()

        # Add rules for error sets
        self.add_chunk_rule(
            ChunkRule(
                node_types={"error_set_declaration"},
                include_children=False,
                priority=5,
                metadata={"type": "error_set"},
            ),
        )

        # Add rules for inline assembly
        self.add_chunk_rule(
            ChunkRule(
                node_types={"asm_expression"},
                include_children=True,
                priority=4,
                metadata={"type": "inline_assembly"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("line_comment")
        self.add_ignore_type("container_doc_comment")

# Register the Zig configuration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

# Plugin implementation for backward compatibility
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

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Zig node."""
        # For most declarations, look for an identifier child
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            # For test declarations, look for string literal
            if node.type == "test_declaration" and child.type == "string_literal":
                # Remove quotes from test name
                test_name = source[child.start_byte : child.end_byte].decode("utf-8")
                return test_name.strip('"')
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Zig."""
        chunks = []

        def extract_chunks(n: Node, container_name: str | None = None):
            # Function declarations
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

                # Check if it's a public function
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

            # Struct declarations
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

                # Process nested functions within struct
                for child in n.children:
                    extract_chunks(child, name)

            # Enum declarations
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

            # Test declarations
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

            # Union declarations
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

                # Process nested functions within union
                for child in n.children:
                    extract_chunks(child, name)

            # Error set declarations
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

            # Comptime declarations
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

            # Continue traversal for nested structures
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
        # All default chunk types should be chunked
        if node.type in self.default_chunk_types:
            return True

        # Inline assembly blocks
        if node.type == "asm_expression":
            return True

        # Const/var declarations with complex initializers
        if node.type in {"const_declaration", "var_declaration"}:
            # Check if it has a function or struct as initializer
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
        name = self.get_node_name(node, source)

        if node.type == "function_declaration":
            # Check for visibility
            is_public = any(
                child.type == "pub"
                or (
                    child.type == "visibility_modifier"
                    and source[child.start_byte : child.end_byte] == b"pub"
                )
                for child in node.children
            )
            visibility = "pub " if is_public else ""
            return f"{visibility}fn {name}" if name else f"{visibility}fn"

        if node.type == "struct_declaration":
            return f"struct {name}" if name else "struct"

        if node.type == "enum_declaration":
            return f"enum {name}" if name else "enum"

        if node.type == "union_declaration":
            return f"union {name}" if name else "union"

        if node.type == "test_declaration":
            return f'test "{name}"' if name else "test"

        if node.type == "error_set_declaration":
            return f"error {name}" if name else "error"

        if node.type == "comptime_declaration":
            return f"comptime {name}" if name else "comptime"

        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Zig nodes with special handling for visibility and tests."""
        # Handle function declarations with visibility
        if node.type == "function_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                # Check for public visibility
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

        # Handle test declarations
        elif node.type == "test_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "test"
                # Extract test name
                test_name = self.get_node_name(node, source)
                if test_name:
                    chunk.metadata = {"test_name": test_name}
                return chunk if self.should_include_chunk(chunk) else None

        # Handle inline assembly
        elif node.type == "asm_expression":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "inline_assembly"
                return chunk if self.should_include_chunk(chunk) else None

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
