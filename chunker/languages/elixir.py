"""
Support for Elixir language.
"""

from __future__ import annotations

from tree_sitter import Node

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class ElixirConfig(LanguageConfig):
    """Language configuration for Elixir."""

    @property
    def language_id(self) -> str:
        return "elixir"

    @property
    def chunk_types(self) -> set[str]:
        """Elixir-specific chunk types."""
        return {
            # Functions
            "function_definition",
            "anonymous_function",
            "call",  # for public/private function definitions
            # Modules
            "module_definition",
            "module_attribute",
            # Macros
            "macro_definition",
            "unquote",
            "quote",
            # Specs and types
            "spec_definition",
            "type_definition",
            "callback_definition",
            # Other constructs
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

        # Add rules for pattern matching
        self.add_chunk_rule(
            ChunkRule(
                node_types={"case", "cond", "with"},
                include_children=True,
                priority=5,
                metadata={"type": "pattern_matching"},
            ),
        )

        # Add rules for GenServer callbacks
        self.add_chunk_rule(
            ChunkRule(
                node_types={"handle_call", "handle_cast", "handle_info"},
                include_children=False,
                priority=6,
                metadata={"type": "genserver_callback"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("atom")


# Register the Elixir configuration

from . import language_config_registry

language_config_registry.register(ElixirConfig(), aliases=["ex"])


# Plugin implementation for backward compatibility
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

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from an Elixir node."""
        # For function definitions (def/defp)
        if node.type == "call":
            # Check if it's a function definition
            for child in node.children:
                if child.type == "identifier":
                    fn_type = source[child.start_byte : child.end_byte].decode("utf-8")
                    if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                        # Look for function name
                        for sibling in node.children:
                            if sibling.type == "call" and sibling != child:
                                for subchild in sibling.children:
                                    if subchild.type == "identifier":
                                        return source[
                                            subchild.start_byte : subchild.end_byte
                                        ].decode("utf-8")
        # For modules
        elif node.type == "module_definition":
            for child in node.children:
                if child.type == "alias":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        # For specs
        elif node.type == "spec_definition":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Elixir."""
        chunks = []

        def extract_chunks(n: Node, parent_module: str | None = None):
            # Special handling for function definitions
            if n.type == "call":
                for child in n.children:
                    if child.type == "identifier":
                        fn_type = source[child.start_byte : child.end_byte].decode(
                            "utf-8",
                        )
                        if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                            content = source[n.start_byte : n.end_byte].decode(
                                "utf-8",
                                errors="replace",
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

            # Regular chunk extraction
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

                # Add metadata
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

            # Track module context
            module_name = parent_module
            if n.type == "module_definition":
                module_name = self.get_node_name(n, source)

            for child in n.children:
                extract_chunks(child, module_name)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Elixir-specific node types that form chunks."""
        return self.default_chunk_types | {
            "call",
        }  # Include call for function definitions

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # Check for function definition calls
        if node.type == "call":
            for child in node.children:
                if child.type == "identifier":
                    fn_type = (
                        child.text.decode("utf-8") if hasattr(child, "text") else ""
                    )
                    if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                        return True
        # All other main declaration types
        if node.type in self.default_chunk_types:
            return True
        # Pattern matching constructs
        if node.type in {"case", "cond", "with"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type == "module_definition":
            return f"defmodule {name}" if name else "module"
        if node.type == "function_definition" or (
            node.type == "call" and self.should_chunk_node(node)
        ):
            return f"def {name}" if name else "function"
        if node.type == "macro_definition":
            return f"defmacro {name}" if name else "macro"
        if node.type == "spec_definition":
            return f"@spec {name}" if name else "spec"
        if node.type == "type_definition":
            return f"@type {name}" if name else "type"
        if node.type == "protocol_definition":
            return f"defprotocol {name}" if name else "protocol"
        if node.type == "implementation_definition":
            return "defimpl"
        if node.type == "struct_definition":
            return "defstruct"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Elixir nodes with special handling for function definitions."""
        # Handle function definitions (def/defp/defmacro/defmacrop)
        if node.type == "call":
            for child in node.children:
                if child.type == "identifier":
                    fn_type = source[child.start_byte : child.end_byte].decode("utf-8")
                    if fn_type in {"def", "defp", "defmacro", "defmacrop"}:
                        chunk = self.create_chunk(
                            node,
                            source,
                            file_path,
                            parent_context,
                        )
                        if chunk:
                            chunk.node_type = "function_definition"
                            # Add visibility metadata
                            if fn_type.endswith("p"):
                                chunk.metadata = {"visibility": "private"}
                            else:
                                chunk.metadata = {"visibility": "public"}
                            if "macro" in fn_type:
                                chunk.metadata["is_macro"] = True
                            return chunk if self.should_include_chunk(chunk) else None

        # Handle module attributes
        if node.type == "module_attribute":
            # Check if it's a behavior/behaviour declaration
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if content.startswith(("@behaviour", "@behavior")):
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = "behaviour_definition"
                    return chunk if self.should_include_chunk(chunk) else None

        # Handle pattern matching with multiple clauses
        if node.type in {"case", "cond", "with"}:
            # Only chunk if complex enough
            if len(node.children) > 3:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk and self.should_include_chunk(chunk):
                    chunk.node_type = f"{node.type}_expression"
                    return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
