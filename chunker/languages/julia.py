"""
Support for Julia language.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class JuliaConfig(LanguageConfig):
    """Language configuration for Julia."""

    @property
    def language_id(self) -> str:
        return "julia"

    @property
    def chunk_types(self) -> set[str]:
        """Julia-specific chunk types."""
        return {"function_definition", "short_function_definition",
            "macro_definition", "struct_definition",
            "abstract_type_definition", "primitive_type_definition",
            "module_definition", "const_statement", "comment", "block_comment"}

    @property
    def file_extensions(self) -> set[str]:
        return {".jl"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(ChunkRule(node_types={"assignment"},
            include_children=True, priority=5, metadata={"type":
            "method_definition"}))
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("identifier")

    @staticmethod
    def _is_method_definition(node: Node, _source: bytes) -> bool:
        """Check if an assignment is a method definition with type annotations."""
        for child in node.children:
            if child.type in {"function_definition",
                "short_function_definition"}:
                for subchild in child.children:
                    if subchild.type == "parameter_list":
                        for param in subchild.children:
                            if param.type == "typed_parameter":
                                return True
        return False


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
        return {"function_definition", "short_function_definition",
            "macro_definition", "struct_definition",
            "abstract_type_definition", "primitive_type_definition",
            "module_definition", "const_statement", "comment", "block_comment"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract the name from a Julia node."""
        if node.type in {"function_definition", "short_function_definition"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
                if child.type == "call_expression":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[subchild.start_byte:subchild.end_byte
                                ].decode("utf-8")
        elif node.type == "macro_definition":
            for child in node.children:
                if child.type == "identifier":
                    return "@" + source[child.start_byte:child.end_byte
                        ].decode("utf-8")
        elif node.type in {"struct_definition", "abstract_type_definition",
            "primitive_type_definition"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
                if child.type == "parameterized_identifier":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[subchild.start_byte:subchild.end_byte
                                ].decode("utf-8")
        elif node.type == "module_definition":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type == "const_statement":
            for child in node.children:
                if child.type == "assignment":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[subchild.start_byte:subchild.end_byte
                                ].decode("utf-8")
                        break
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Julia."""
        chunks = []

        def extract_chunks(n: Node, module_context: (str | None) = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": n.type, "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                if module_context:
                    chunk["module"] = module_context
                if n.type == "struct_definition":
                    chunk["is_mutable"] = "mutable" in content.split()[0:2]
                elif n.type == "short_function_definition":
                    chunk["is_one_liner"] = True
                chunks.append(chunk)
                if n.type == "module_definition":
                    module_context = self.get_node_name(n, source)
            for child in n.children:
                extract_chunks(child, module_context)
        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Julia-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type.endswith("_definition"):
            return True
        return node.type in {"const_statement", "comment", "block_comment"}

    def get_node_context(self, node: Node, source: bytes) -> (str | None):
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)
        if node.type in {"function_definition", "short_function_definition"}:
            if name:
                return f"function {name}"
            return "function"
        if node.type == "macro_definition":
            if name:
                return f"macro {name}"
            return "macro"
        if node.type == "struct_definition":
            if name:
                content = source[node.start_byte:node.end_byte].decode("utf-8")
                if content.strip().startswith("mutable"):
                    return f"mutable struct {name}"
                return f"struct {name}"
            return "struct"
        if node.type == "abstract_type_definition":
            if name:
                return f"abstract type {name}"
            return "abstract type"
        if node.type == "primitive_type_definition":
            if name:
                return f"primitive type {name}"
            return "primitive type"
        if node.type == "module_definition":
            if name:
                return f"module {name}"
            return "module"
        if node.type == "const_statement":
            if name:
                return f"const {name}"
            return "const"
        return None

    def process_node(self, node: Node, source: bytes, file_path: str,
        parent_context: (str | None) = None):
        """Process Julia nodes with special handling for nested structures."""
        if node.type == "module_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                module_name = self.get_node_name(node, source)
                if module_name:
                    parent_context = f"module:{module_name}"
                return chunk
        if node.type == "struct_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                content = source[node.start_byte:node.end_byte].decode("utf-8")
                if content.strip().startswith("mutable"):
                    chunk.node_type = "mutable_struct_definition"
                return chunk
        if node.type == "short_function_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.metadata = {"one_liner": True}
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        if node.type == "module_definition":
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"module:{name}"
        if node.type in {"struct_definition", "mutable_struct_definition"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"struct:{name}"
        return chunk.node_type
