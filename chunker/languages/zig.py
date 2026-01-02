"""
Support for Zig language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode_bytes

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
            "assignment_statement",  # For const/var declarations that define structs, enums etc
            "test_expression",
            "comptime_block",
            "struct_declaration",  # Add for test compatibility
            "enum_declaration",  # Add for test compatibility
            "union_declaration",  # Add for test compatibility
            "error_set_declaration",  # Add for test compatibility
            "test_declaration",  # Add for test compatibility
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Zig node."""
        if node.type == "test_expression":
            # For test expressions, find the string literal
            for child in node.children:
                if child.type == "string_literal":
                    test_name = safe_decode_bytes(
                        source[child.start_byte : child.end_byte],
                    )
                    return test_name.strip('"')
            return None

        # For other nodes, find the identifier
        for child in node.children:
            if child.type == "identifier":
                return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Zig."""
        chunks = []
        processed_nodes = set()  # Track processed function nodes to avoid duplicates

        def extract_chunks(n: Node, container_name: str | None = None):
            if n.type == "function_declaration" and n not in processed_nodes:
                processed_nodes.add(n)
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])
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
            elif n.type == "ERROR":
                # Handle functions within ERROR nodes (due to parsing issues)
                self._extract_function_from_error_node(
                    n,
                    source,
                    chunks,
                    processed_nodes,
                    container_name,
                )
            elif n.type == "assignment_statement":
                # Check for struct, enum, union definitions
                name = None
                chunk_type = None
                container_expr = None
                for child in n.children:
                    if child.type == "identifier":
                        name = safe_decode_bytes(
                            source[child.start_byte : child.end_byte]
                        )
                    elif child.type == "struct_expression":
                        chunk_type = "struct"
                        container_expr = child
                    elif child.type == "enum_expression":
                        chunk_type = "enum"
                        container_expr = child
                    elif child.type == "union_expression":
                        chunk_type = "union"
                        container_expr = child
                    elif child.type == "error_expression":
                        chunk_type = "error_set"

                if chunk_type and name:
                    content = safe_decode_bytes(source[n.start_byte : n.end_byte])
                    chunk = {
                        "type": chunk_type,
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "content": content,
                        "name": name,
                    }
                    chunks.append(chunk)

                    # For struct/enum/union, extract nested functions with container context
                    if container_expr:
                        extract_chunks(container_expr, name)
                        return  # Don't recurse further to avoid double-processing

            elif n.type == "test_expression":
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "test",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                chunks.append(chunk)
            elif n.type == "comptime_block":
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])
                chunk = {
                    "type": "comptime",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": None,
                }
                chunks.append(chunk)

            # Recurse into children for other nodes (unless we handled assignment_statement above)
            if n.type != "assignment_statement" or not chunk_type:
                for child in n.children:
                    extract_chunks(child, container_name)

        extract_chunks(node)
        return chunks

    def _extract_function_from_error_node(
        self,
        error_node: Node,
        source: bytes,
        chunks: list,
        processed_nodes: set,
        container_name: str | None = None,
    ):
        """Extract function patterns from ERROR nodes caused by parsing issues."""
        # Look for function patterns: pub/visibility_modifier + fn + identifier
        children = list(error_node.children)

        i = 0
        while i < len(children):
            # Look for function pattern
            is_public = False
            fn_start_idx = i

            # Check for visibility modifier
            if i < len(children) and (
                children[i].type == "visibility_modifier" or children[i].type == "pub"
            ):
                is_public = True
                i += 1

            # Check for 'fn' keyword
            if i < len(children) and children[i].type == "fn":
                # Look for identifier after 'fn'
                if i + 1 < len(children) and children[i + 1].type == "identifier":
                    # We found a function pattern, now find the end
                    func_name = safe_decode_bytes(
                        source[children[i + 1].start_byte : children[i + 1].end_byte],
                    )

                    # Find the function body by looking for balanced braces
                    func_end_idx = self._find_function_end(children, i + 2)
                    if func_end_idx > i:
                        # Create function chunk
                        start_node = children[fn_start_idx]
                        end_node = children[func_end_idx]
                        content = safe_decode_bytes(
                            source[start_node.start_byte : end_node.end_byte],
                        )

                        # Create a synthetic node ID for deduplication
                        synthetic_id = (start_node.start_byte, end_node.end_byte)
                        if synthetic_id not in processed_nodes:
                            processed_nodes.add(synthetic_id)

                            chunk = {
                                "type": "function",
                                "start_line": start_node.start_point[0] + 1,
                                "end_line": end_node.end_point[0] + 1,
                                "content": content,
                                "name": func_name,
                                "visibility": "public" if is_public else "private",
                            }
                            if container_name:
                                chunk["container"] = container_name
                            chunks.append(chunk)

                        i = func_end_idx + 1
                        continue
            i += 1

    def _find_function_end(self, children: list, start_idx: int) -> int:
        """Find the end of a function by looking for balanced braces."""
        brace_count = 0
        found_opening_brace = False

        for i in range(start_idx, len(children)):
            child = children[i]
            if child.type == "{":
                brace_count += 1
                found_opening_brace = True
            elif child.type == "}":
                brace_count -= 1
                if found_opening_brace and brace_count == 0:
                    return i
            elif child.type == "ERROR" and found_opening_brace:
                # Look for closing brace within ERROR node
                for error_child in child.children:
                    if error_child.type == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            return i

        # If we can't find balanced braces, look for the next function or top-level construct
        for i in range(start_idx, len(children)):
            child = children[i]
            if child.type in {"test_expression", "assignment_statement"}:
                return i - 1 if i > start_idx else start_idx

        return len(children) - 1 if len(children) > start_idx else start_idx

    def get_chunk_node_types(self) -> set[str]:
        """Get Zig-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type == "function_declaration":
            return True
        if node.type == "test_expression":
            return True
        if node.type == "assignment_statement":
            # Check if it's defining a struct, enum, etc.
            for child in node.children:
                if child.type in {
                    "struct_expression",
                    "enum_expression",
                    "union_expression",
                    "error_expression",
                }:
                    return True
        if node.type == "comptime_block":
            return True
        if node.type == "asm_expression":
            return True
        # Handle the test compatibility node types (even though they map to actual types)
        if node.type in {
            "struct_declaration",
            "enum_declaration",
            "union_declaration",
            "error_set_declaration",
            "test_declaration",
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
