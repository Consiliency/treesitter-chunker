"""
Support for Elixir language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode, safe_decode_bytes

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class ElixirConfig(LanguageConfig):
    """Language configuration for Elixir."""

    @property
    def language_id(self) -> str:
        return "elixir"

    @property
    def chunk_types(self) -> set[str]:
        """Elixir-specific chunk types."""
        return {
            "function_definition",
            "anonymous_function",
            "call",
            "module_definition",
            "module_attribute",
            "macro_definition",
            "unquote",
            "quote",
            "spec_definition",
            "type_definition",
            "callback_definition",
            "protocol_definition",
            "implementation_definition",
            "struct_definition",
            "behaviour_definition",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".ex", ".exs"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"case", "cond", "with"},
                include_children=True,
                priority=5,
                metadata={"type": "pattern_matching"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"handle_call", "handle_cast", "handle_info"},
                include_children=False,
                priority=6,
                metadata={"type": "genserver_callback"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("atom")


# Register the Elixir configuration
from .base import language_config_registry

elixir_config = ElixirConfig()
language_config_registry.register(elixir_config)


class ElixirPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Elixir language chunking."""

    @property
    def language_name(self) -> str:
        return "elixir"

    @property
    def supported_extensions(self) -> set[str]:
        return {".ex", ".exs"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "anonymous_function",
            "module_definition",
            "macro_definition",
            "spec_definition",
            "type_definition",
            "callback_definition",
            "protocol_definition",
            "implementation_definition",
            "struct_definition",
            "behaviour_definition",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from an Elixir node."""
        if node.type == "call":
            return ElixirPlugin._get_call_node_name(node, source)
        if node.type == "module_definition":
            return ElixirPlugin._get_module_definition_name(node, source)
        if node.type == "spec_definition":
            return ElixirPlugin._get_spec_definition_name(node, source)
        return None

    @staticmethod
    def _get_call_node_name(node: Node, source: bytes) -> str | None:
        """Extract name from a call node (def, defp, defmacro, defmacrop)."""
        # Find the function type identifier
        fn_type_node = None
        for child in node.children:
            if child.type == "identifier":
                fn_type = safe_decode_bytes(source[child.start_byte : child.end_byte])
                if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                    fn_type_node = child
                    break

        if not fn_type_node:
            return None

        # Find the function name in sibling call nodes
        for sibling in node.children:
            if sibling.type != "call" or sibling == fn_type_node:
                continue

            name = ElixirPlugin._extract_identifier_from_node(sibling, source)
            if name:
                return name

        return None

    @staticmethod
    def _get_module_definition_name(node: Node, source: bytes) -> str | None:
        """Extract name from a module definition node."""
        for child in node.children:
            if child.type == "alias":
                return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    @staticmethod
    def _get_spec_definition_name(node: Node, source: bytes) -> str | None:
        """Extract name from a spec definition node."""
        for child in node.children:
            if child.type == "identifier":
                return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    @staticmethod
    def _extract_identifier_from_node(node: Node, source: bytes) -> str | None:
        """Extract the first identifier from a node's children."""
        for child in node.children:
            if child.type == "identifier":
                return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Elixir."""
        chunks = []

        def extract_chunks(n: Node, parent_module: str | None = None):
            if n.type == "call":
                for child in n.children:
                    if child.type == "identifier":
                        fn_type = safe_decode_bytes(
                            source[child.start_byte : child.end_byte]
                        )
                        if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                            content = safe_decode_bytes(
                                source[n.start_byte : n.end_byte]
                            )
                            chunk = {
                                "type": "function_definition",
                                "start_line": n.start_point[0] + 1,
                                "end_line": n.end_point[0] + 1,
                                "content": content,
                                "name": self.get_node_name(n, source),
                                "visibility": (
                                    "private" if fn_type.endswith("p") else "public"
                                ),
                                "is_macro": "macro" in fn_type,
                            }
                            if parent_module:
                                chunk["module"] = parent_module
                            chunks.append(chunk)
                            return
            if n.type in self.default_chunk_types:
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if n.type == "module_definition":
                    chunk["is_module"] = True
                    parent_module = self.get_node_name(n, source)
                elif n.type == "anonymous_function":
                    chunk["is_lambda"] = True
                elif n.type == "spec_definition":
                    chunk["is_spec"] = True
                if parent_module:
                    chunk["module"] = parent_module
                chunks.append(chunk)
            module_name = parent_module
            if n.type == "module_definition":
                module_name = self.get_node_name(n, source)
            for child in n.children:
                extract_chunks(child, module_name)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Elixir-specific node types that form chunks."""
        return self.default_chunk_types | {"call"}

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type == "call":
            for child in node.children:
                if child.type == "identifier":
                    fn_type = (
                        safe_decode(child.text) if hasattr(child, "text") else ""
                    )
                    if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                        return True
        if node.type in self.default_chunk_types:
            return True
        if node.type in {"case", "cond", "with"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Handle special case for function calls that should be chunked
        if node.type == "call" and self.should_chunk_node(node):
            name = self.get_node_name(node, source)
            return f"def {name}" if name else "function"

        # Map node types to their context format (prefix, default, needs_name)
        node_context_map = {
            "module_definition": ("defmodule", "module", True),
            "function_definition": ("def", "function", True),
            "macro_definition": ("defmacro", "macro", True),
            "spec_definition": ("@spec", "spec", True),
            "type_definition": ("@type", "type", True),
            "protocol_definition": ("defprotocol", "protocol", True),
            "implementation_definition": (None, "defimpl", False),
            "struct_definition": (None, "defstruct", False),
        }

        if node.type not in node_context_map:
            return None

        prefix, default, needs_name = node_context_map[node.type]
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
        """Process Elixir nodes with special handling for function definitions."""
        # Handle function/macro definitions
        if node.type == "call":
            result = self._process_call_node(node, source, file_path, parent_context)
            if result:
                return result

        # Handle module attributes
        if node.type == "module_attribute":
            result = self._process_module_attribute(
                node,
                source,
                file_path,
                parent_context,
            )
            if result:
                return result

        # Handle pattern matching expressions
        if node.type in {"case", "cond", "with"} and len(node.children) > 3:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.node_type = f"{node.type}_expression"
                return chunk

        return super().process_node(node, source, file_path, parent_context)

    def _process_call_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None,
    ):
        """Process call nodes for function/macro definitions."""
        # Check if this is a function/macro definition
        fn_type = ElixirPlugin._get_function_type(node, source)
        if not fn_type:
            return None

        # Create the chunk
        chunk = self.create_chunk(node, source, file_path, parent_context)
        if not chunk:
            return None

        # Set chunk metadata
        chunk.node_type = "function_definition"
        chunk.metadata = self._get_function_metadata(fn_type)

        return chunk if self.should_include_chunk(chunk) else None

    @staticmethod
    def _get_function_type(node: Node, source: bytes) -> str | None:
        """Extract function type (def/defp/defmacro/defmacrop) from call node."""
        for child in node.children:
            if child.type != "identifier":
                continue

            fn_type = safe_decode_bytes(source[child.start_byte : child.end_byte])
            if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                return fn_type

        return None

    @staticmethod
    def _get_function_metadata(fn_type: str) -> dict[str, any]:
        """Get metadata for a function based on its type."""
        metadata = {
            "visibility": "private" if fn_type.endswith("p") else "public",
        }
        if "macro" in fn_type:
            metadata["is_macro"] = True
        return metadata

    def _process_module_attribute(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None,
    ):
        """Process module attribute nodes."""
        content = safe_decode_bytes(source[node.start_byte : node.end_byte])
        if not content.startswith(("@behaviour", "@behavior")):
            return None

        chunk = self.create_chunk(node, source, file_path, parent_context)
        if not chunk:
            return None

        chunk.node_type = "behaviour_definition"
        return chunk if self.should_include_chunk(chunk) else None
