"""
Support for Haskell language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode_bytes

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
            "signature",  # type signatures
            "data_type",
            "data_constructor",
            "newtype",
            "type_synomym",  # type aliases (grammar has misspelling)
            "class",  # type class definitions
            "instance",
            "header",  # module declaration
            "import",
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
            "signature",  # type signatures
            "data_type",
            "data_constructor",
            "newtype",
            "type_synomym",  # type aliases (grammar has misspelling)
            "class",  # type class definitions
            "instance",
            "header",  # module declaration
            "import",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Haskell node."""
        if node.type in {"function", "signature"}:
            for child in node.children:
                if child.type == "variable":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type == "data_type" or node.type == "class":
            for child in node.children:
                if child.type == "name":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type == "header":
            # Extract module name from module header
            for child in node.children:
                if child.type == "module" and hasattr(child, "children"):
                    for grandchild in child.children:
                        if grandchild.type == "module_id":
                            return safe_decode_bytes(
                                source[grandchild.start_byte : grandchild.end_byte]
                            )
        elif node.type == "import":
            # Extract imported module name
            for child in node.children:
                if child.type == "module":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Haskell."""
        chunks = []

        def extract_chunks(n: Node, parent_context: str | None = None):
            if n.type in self.default_chunk_types:
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])

                # Map node types for compatibility with tests
                chunk_type = n.type
                if n.type == "header":
                    chunk_type = "module_declaration"
                elif n.type == "class":
                    chunk_type = "class_declaration"

                chunk = {
                    "type": chunk_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }

                # Add semantic metadata
                if n.type == "function":
                    chunk["is_function"] = True
                    if parent_context == "signature":
                        chunk["has_type_signature"] = True
                elif n.type == "signature":
                    chunk["is_type_signature"] = True
                elif n.type == "data_type":
                    chunk["is_type_definition"] = True
                elif n.type == "class":
                    chunk["is_typeclass"] = True
                elif n.type == "header":
                    chunk["is_module_declaration"] = True
                elif n.type == "import":
                    chunk["is_import"] = True

                chunks.append(chunk)

            new_context = n.type if n.type in {"signature", "where"} else parent_context
            for child in n.children:
                extract_chunks(child, new_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Haskell-specific node types that form chunks."""
        # Return the mapped types that tests expect
        mapped_types = set()
        for node_type in self.default_chunk_types:
            if node_type == "header":
                mapped_types.add("module_declaration")
            elif node_type == "class":
                mapped_types.add("class_declaration")
            elif node_type == "instance":
                mapped_types.add("instance_declaration")
            elif node_type == "type_synomym":
                mapped_types.add("type_synonym")
            else:
                mapped_types.add(node_type)
        return mapped_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # Handle both original node types and mapped types
        if node.type in self.default_chunk_types:
            return True
        # Handle mapped types that tests might pass in
        if hasattr(node, "type"):
            mapped_type = node.type
            if mapped_type == "module_declaration":
                return "header" in self.default_chunk_types
            if mapped_type == "class_declaration":
                return "class" in self.default_chunk_types
            if mapped_type == "instance_declaration":
                return "instance" in self.default_chunk_types
            if mapped_type == "type_synonym":
                return "type_synomym" in self.default_chunk_types
        if node.type in {"let_bindings", "where"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format (prefix, default, needs_name)
        node_context_map = {
            "function": ("function", "function", True),
            "signature": ("signature", "type signature", True),
            "data_type": ("data", "data type", True),
            "newtype": ("newtype", "newtype", True),
            "class": ("class", "typeclass", True),
            "instance": ("instance", "instance", True),
            "header": (None, "module declaration", False),
            "import": ("import", "import", True),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        prefix, default, needs_name = context_info
        if not needs_name or prefix is None:
            return default

        name = self.get_node_name(node, source)
        return f"{prefix} {name}" if name else default

    def create_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Create a CodeChunk from a node with Haskell-specific type mapping."""
        content = safe_decode_bytes(source[node.start_byte : node.end_byte])

        # Map node types for compatibility with tests
        chunk_type = node.type
        if node.type == "header":
            chunk_type = "module_declaration"
        elif node.type == "class":
            chunk_type = "class_declaration"

        from chunker.types import CodeChunk

        return CodeChunk(
            language=self.language_name,
            file_path=file_path,
            node_type=chunk_type,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
            parent_context=parent_context or "",
            content=content,
        )

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
                if prev_sibling and prev_sibling.type == "signature":
                    combined_start = prev_sibling.start_byte
                    combined_end = node.end_byte
                    combined_content = safe_decode_bytes(
                        source[combined_start:combined_end]
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
            child.type == "function" for child in node.children
        ):
            return super().process_node(
                node,
                source,
                file_path,
                parent_context,
            )
        return super().process_node(node, source, file_path, parent_context)
