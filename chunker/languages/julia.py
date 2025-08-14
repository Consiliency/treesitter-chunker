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
        return {
            "function_definition",
            "short_function_definition",
            "assignment",  # one-liner functions
            "macro_definition",
            "macrocall_expression",  # @generated functions, etc.
            "struct_definition",
            "abstract_definition",  # abstract type definitions
            "primitive_definition",  # primitive type definitions
            "module_definition",
            "const_statement",
            "comment",
            "line_comment",  # single-line comments
            "block_comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".jl"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"assignment"},
                include_children=True,
                priority=5,
                metadata={"type": "method_definition"},
            ),
        )
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("identifier")

    @staticmethod
    def _is_method_definition(node: Node, _source: bytes) -> bool:
        """Check if an assignment is a method definition with type annotations."""
        for child in node.children:
            if child.type in {
                "function_definition",
                "short_function_definition",
            } and JuliaConfig._has_typed_parameters(child):
                return True
        return False

    @staticmethod
    def _has_typed_parameters(function_node: Node) -> bool:
        """Check if function has typed parameters."""
        for child in function_node.children:
            if child.type != "parameter_list":
                continue

            for param in child.children:
                if param.type == "typed_parameter":
                    return True
        return False


# Register the Julia configuration


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
            "assignment",  # one-liner functions
            "macro_definition",
            "macrocall_expression",  # @generated functions, etc.
            "struct_definition",
            "abstract_definition",  # abstract type definitions
            "primitive_definition",  # primitive type definitions
            "module_definition",
            "const_statement",
            "comment",
            "line_comment",  # single-line comments
            "block_comment",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Julia node."""
        # Map node types to their name extraction logic
        node_name_extractors = {
            "function_definition": JuliaPlugin._extract_function_name,
            "short_function_definition": JuliaPlugin._extract_function_name,
            "assignment": JuliaPlugin._extract_assignment_name,
            "macro_definition": JuliaPlugin._extract_macro_name,
            "macrocall_expression": JuliaPlugin._extract_macrocall_name,
            "struct_definition": JuliaPlugin._extract_type_name,
            "abstract_definition": JuliaPlugin._extract_type_name,
            "primitive_definition": JuliaPlugin._extract_type_name,
            "module_definition": JuliaPlugin._extract_module_name,
            "const_statement": JuliaPlugin._extract_const_name,
        }

        extractor = node_name_extractors.get(node.type)
        return extractor(node, source) if extractor else None

    @staticmethod
    def _extract_function_name(node: Node, source: bytes) -> str | None:
        """Extract name from function definitions."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if child.type == "call_expression":
                for subchild in child.children:
                    if subchild.type == "identifier":
                        return source[subchild.start_byte : subchild.end_byte].decode(
                            "utf-8",
                        )
        return None

    @staticmethod
    def _extract_assignment_name(node: Node, source: bytes) -> str | None:
        """Extract name from assignment nodes (one-liner functions)."""
        for child in node.children:
            if child.type == "call_expression":
                # This is a function assignment like f(x) = x + 1
                for subchild in child.children:
                    if subchild.type == "identifier":
                        return source[subchild.start_byte : subchild.end_byte].decode(
                            "utf-8",
                        )
        return None

    @staticmethod
    def _extract_macro_name(node: Node, source: bytes) -> str | None:
        """Extract name from macro definitions."""
        for child in node.children:
            if child.type == "identifier":
                return "@" + source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    @staticmethod
    def _extract_macrocall_name(node: Node, source: bytes) -> str | None:
        """Extract name from macrocall expressions (e.g., @generated function)."""
        # For @generated function mysum(...), extract "mysum"
        for child in node.children:
            if child.type == "macro_argument_list":
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        return JuliaPlugin._extract_function_name(subchild, source)
        return None

    @staticmethod
    def _extract_type_name(node: Node, source: bytes) -> str | None:
        """Extract name from type definitions."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
            if child.type == "parameterized_identifier":
                for subchild in child.children:
                    if subchild.type == "identifier":
                        return source[subchild.start_byte : subchild.end_byte].decode(
                            "utf-8",
                        )
        return None

    @staticmethod
    def _extract_module_name(node: Node, source: bytes) -> str | None:
        """Extract name from module definitions."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    @staticmethod
    def _extract_const_name(node: Node, source: bytes) -> str | None:
        """Extract name from const statements."""
        for child in node.children:
            if child.type == "assignment":
                for subchild in child.children:
                    if subchild.type == "identifier":
                        return source[subchild.start_byte : subchild.end_byte].decode(
                            "utf-8",
                        )
                    break
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Julia."""
        chunks = []

        def extract_chunks(n: Node, module_context: str | None = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )

                # Map assignment nodes that are function definitions
                chunk_type = n.type
                if n.type == "assignment":
                    # Check if this is a function assignment
                    for child in n.children:
                        if child.type == "call_expression":
                            chunk_type = "short_function_definition"
                            break

                chunk = {
                    "type": chunk_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if module_context:
                    chunk["module"] = module_context
                if n.type == "struct_definition":
                    chunk["is_mutable"] = "mutable" in content.split()[0:2]
                elif chunk_type == "short_function_definition":
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

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Special handling for struct_definition to check mutability
        if node.type == "struct_definition":
            name = self.get_node_name(node, source)
            if name:
                content = source[node.start_byte : node.end_byte].decode("utf-8")
                prefix = (
                    "mutable struct"
                    if content.strip().startswith("mutable")
                    else "struct"
                )
                return f"{prefix} {name}"
            return "struct"

        # Map node types to their context format (prefix, default)
        node_context_map = {
            "function_definition": ("function", "function"),
            "short_function_definition": ("function", "function"),
            "macro_definition": ("macro", "macro"),
            "abstract_type_definition": ("abstract type", "abstract type"),
            "primitive_type_definition": ("primitive type", "primitive type"),
            "module_definition": ("module", "module"),
            "const_statement": ("const", "const"),
        }

        if node.type not in node_context_map:
            return None

        prefix, default = node_context_map[node.type]
        name = self.get_node_name(node, source)
        return f"{prefix} {name}" if name else default

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
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
                content = source[node.start_byte : node.end_byte].decode("utf-8")
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
