"""
Support for Haskell language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class HaskellConfig(LanguageConfig):
    """Language configuration for Haskell."""

    @property
    def language_id(self) -> str:
        return "haskell"

    @property
    def chunk_types(self) -> set[str]:
        """Haskell-specific chunk types."""
        return {
            "function",
            "function_declaration",
            "function_body",
            "type_alias",
            "type_synonym",
            "type_synomym",  # some grammar versions use this misspelling
            "data_type",
            "data_constructor",
            "newtype",
            "type_declaration",
            # Grammar may emit either canonical or short forms
            "class_declaration",
            "instance_declaration",
            "class",
            "instance",
            "module_declaration",
            "import_declaration",
            "pragma",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".hs", ".lhs"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"where_clause"},
                include_children=True,
                priority=5,
                metadata={"type": "where_bindings"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"case_expression", "guards"},
                include_children=False,
                priority=4,
                metadata={"type": "pattern_matching"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("integer")


# Register the Haskell configuration


class HaskellPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Haskell language chunking."""

    @property
    def language_name(self) -> str:
        return "haskell"

    @property
    def supported_extensions(self) -> set[str]:
        return {".hs", ".lhs"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function",
            "function_declaration",
            "function_body",
            "type_alias",
            "type_synonym",
            "type_synomym",  # misspelled variant
            "data_type",
            "data_constructor",
            "newtype",
            # Grammar may emit either canonical or short forms
            "class_declaration",
            "instance_declaration",
            "class",
            "instance",
            "module_declaration",
            "type_declaration",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Haskell node."""
        if node.type in {"function", "function_declaration"}:
            for child in node.children:
                if child.type in {"variable", "variable_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type in {
            "type_alias",
            "type_synonym",
            "type_synomym",
            "type_declaration",
            "data_type",
            "newtype",
        }:
            for child in node.children:
                if child.type in {
                    "type",
                    "type_constructor_identifier",
                    "type_name",
                    "constructor",
                }:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type in {
            "class_declaration",
            "instance_declaration",
            "class",
            "instance",
        }:
            for child in node.children:
                if child.type in {"class_name", "type_class_identifier", "name"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Haskell."""
        chunks = []

        def extract_chunks(n: Node, parent_context: str | None = None):
            if n.type in self.default_chunk_types:
                out_type = n.type
                if n.type == "type_declaration":
                    # Normalize generic type declarations to type_synonym for tests
                    out_type = "type_synonym"
                elif n.type == "type_synomym":
                    # Normalize misspelled grammar node to canonical name
                    out_type = "type_synonym"
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": out_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if out_type == "function":
                    chunk["is_function"] = True
                    if parent_context == "type_signature":
                        chunk["has_type_signature"] = True
                elif out_type in {"type_alias", "type_synonym", "data_type", "newtype"}:
                    chunk["is_type_definition"] = True
                elif out_type in {"class_declaration", "instance_declaration"}:
                    chunk["is_typeclass"] = True
                chunks.append(chunk)
            new_context = (
                n.type
                if n.type
                in {
                    "type_signature",
                    "where",
                }
                else parent_context
            )
            for child in n.children:
                extract_chunks(child, new_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Haskell-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type in {"let_bindings", "where"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format (prefix, default, needs_name)
        node_context_map = {
            "function": ("function", "function", True),
            "type_alias": ("type", "type alias", True),
            "type_synonym": ("type", "type alias", True),
            "data_type": ("data", "data type", True),
            "newtype": ("newtype", "newtype", True),
            "class_declaration": ("class", "typeclass", True),
            "instance_declaration": ("instance", "instance", True),
            "module_declaration": (None, "module declaration", False),
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
        """Process Haskell nodes with special handling for nested definitions."""
        if node.type == "function" and parent_context != "processed":
            parent = node.parent
            if parent:
                prev_sibling = None
                for i, child in enumerate(parent.children):
                    if child == node and i > 0:
                        prev_sibling = parent.children[i - 1]
                        break
                if prev_sibling and prev_sibling.type == "type_signature":
                    combined_start = prev_sibling.start_byte
                    combined_end = node.end_byte
                    combined_content = source[combined_start:combined_end].decode(
                        "utf-8",
                        errors="replace",
                    )
                    chunk = self.create_chunk(node, source, file_path, parent_context)
                    if chunk:
                        chunk.content = combined_content
                        chunk.start_line = prev_sibling.start_point[0] + 1
                        chunk.byte_start = combined_start
                        chunk.node_type = "function_with_signature"
                        return (
                            chunk
                            if self.should_include_chunk(
                                chunk,
                            )
                            else None
                        )
        if node.type == "where" and any(
            child.type in {"function", "function_declaration"}
            for child in node.children
        ):
            return super().process_node(
                node,
                source,
                file_path,
                parent_context,
            )
        return super().process_node(node, source, file_path, parent_context)
