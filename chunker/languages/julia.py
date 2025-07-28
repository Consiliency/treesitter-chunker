"""
Support for Julia language.
"""

from __future__ import annotations

from typing import Optional

from tree_sitter import Node

from ..contracts.language_plugin_contract import ExtendedLanguagePluginContract
from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class JuliaConfig(LanguageConfig):
    """Language configuration for Julia."""

    @property
    def language_id(self) -> str:
        return "julia"

    @property
    def chunk_types(self) -> set[str]:
        """Julia-specific chunk types."""
        return {
            # Functions
            "function_definition",
            "short_function_definition",
            # Macros
            "macro_definition",
            # Types and structs
            "struct_definition",
            "abstract_type_definition",
            "primitive_type_definition",
            # Modules
            "module_definition",
            # Constants
            "const_statement",
            # Comments
            "comment",
            "block_comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".jl"}

    def __init__(self):
        super().__init__()

        # Add rules for method definitions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"assignment"},
                include_children=True,
                priority=5,
                metadata={"type": "method_definition"},
                condition=lambda node, source: self._is_method_definition(node, source),
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("identifier")

    def _is_method_definition(self, node: Node, source: bytes) -> bool:
        """Check if an assignment is a method definition with type annotations."""
        # Look for function definitions with type annotations
        for child in node.children:
            if child.type in {"function_definition", "short_function_definition"}:
                # Check if parameters have type annotations
                for subchild in child.children:
                    if subchild.type == "parameter_list":
                        for param in subchild.children:
                            if param.type == "typed_parameter":
                                return True
        return False


# Register the Julia configuration
from . import language_config_registry

language_config_registry.register(JuliaConfig(), aliases=["jl"])


# Plugin implementation for backward compatibility
class JuliaPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Julia language chunking."""

    @property
    def language_name(self) -> str:
        return "julia"

    @property
    def supported_extensions(self) -> set[str]:
        return {".jl"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "short_function_definition",
            "macro_definition",
            "struct_definition",
            "abstract_type_definition",
            "primitive_type_definition",
            "module_definition",
            "const_statement",
            "comment",
            "block_comment",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Julia node."""
        if node.type in {"function_definition", "short_function_definition"}:
            # Look for function name
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                elif child.type == "call_expression":
                    # Method definition with function call syntax
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif node.type == "macro_definition":
            # Look for macro name after 'macro' keyword
            for child in node.children:
                if child.type == "identifier":
                    return "@" + source[child.start_byte : child.end_byte].decode(
                        "utf-8",
                    )
        elif node.type in {
            "struct_definition",
            "abstract_type_definition",
            "primitive_type_definition",
        }:
            # Look for type name
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                elif child.type == "parameterized_identifier":
                    # Generic type like MyType{T}
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif node.type == "module_definition":
            # Module name
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type == "const_statement":
            # Const variable name
            for child in node.children:
                if child.type == "assignment":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
                        break
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Julia."""
        chunks = []

        def extract_chunks(n: Node, module_context: str = None):
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

                # Add module context if within a module
                if module_context:
                    chunk["module"] = module_context

                # Add metadata for different definition types
                if n.type == "struct_definition":
                    chunk["is_mutable"] = "mutable" in content.split()[0:2]
                elif n.type == "short_function_definition":
                    chunk["is_one_liner"] = True

                chunks.append(chunk)

                # Update module context for children
                if n.type == "module_definition":
                    module_context = self.get_node_name(n, source)

            for child in n.children:
                extract_chunks(child, module_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Julia-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All definition nodes should be chunked
        if node.type.endswith("_definition"):
            return True
        # Constants and comments
        if node.type in {"const_statement", "comment", "block_comment"}:
            return True
        return False

    def get_node_context(self, node: Node, source: bytes) -> Optional[str]:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type in {"function_definition", "short_function_definition"}:
            if name:
                return f"function {name}"
            return "function"
        elif node.type == "macro_definition":
            if name:
                return f"macro {name}"
            return "macro"
        elif node.type == "struct_definition":
            if name:
                # Check if mutable
                content = source[node.start_byte : node.end_byte].decode("utf-8")
                if content.strip().startswith("mutable"):
                    return f"mutable struct {name}"
                return f"struct {name}"
            return "struct"
        elif node.type == "abstract_type_definition":
            if name:
                return f"abstract type {name}"
            return "abstract type"
        elif node.type == "primitive_type_definition":
            if name:
                return f"primitive type {name}"
            return "primitive type"
        elif node.type == "module_definition":
            if name:
                return f"module {name}"
            return "module"
        elif node.type == "const_statement":
            if name:
                return f"const {name}"
            return "const"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Julia nodes with special handling for nested structures."""
        # Handle module definitions with nested content
        if node.type == "module_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Set module name as context for children
                module_name = self.get_node_name(node, source)
                if module_name:
                    parent_context = f"module:{module_name}"
                return chunk

        # Handle struct definitions with fields
        if node.type == "struct_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Check if it's a mutable struct
                content = source[node.start_byte : node.end_byte].decode("utf-8")
                if content.strip().startswith("mutable"):
                    chunk.node_type = "mutable_struct_definition"
                return chunk

        # Handle short function definitions (one-liners)
        if node.type == "short_function_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Mark as one-liner for special handling
                chunk.metadata = {"one_liner": True}
                return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        # For modules, pass the module name to children
        if node.type == "module_definition":
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"module:{name}"

        # For structs, pass struct info
        if node.type in {"struct_definition", "mutable_struct_definition"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"struct:{name}"

        return chunk.node_type
