"""
Support for OCaml language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class OCamlConfig(LanguageConfig):
    """Language configuration for OCaml."""

    @property
    def language_id(self) -> str:
        return "ocaml"

    @property
    def chunk_types(self) -> set[str]:
        """OCaml-specific chunk types."""
        return {
            # Value bindings
            "value_definition",
            "let_binding",
            "let_rec_binding",
            # Function definitions
            "function_definition",
            "fun_expression",
            # Type definitions
            "type_definition",
            "type_binding",
            # Module definitions
            "module_definition",
            "module_binding",
            "signature",
            "structure",
            # Exception definitions
            "exception_definition",
            # Class definitions
            "class_definition",
            "class_binding",
            # Comments
            "comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".ml", ".mli", ".mll", ".mly"}

    def __init__(self):
        super().__init__()

        # Add rules for pattern matching functions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"match_expression", "function_expression"},
                include_children=True,
                priority=5,
                metadata={"type": "pattern_matching"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("constructor")


# Register the OCaml configuration
from typing import TYPE_CHECKING

from . import language_config_registry

if TYPE_CHECKING:
    from tree_sitter import Node

language_config_registry.register(OCamlConfig(), aliases=["ml", "mli"])


# Plugin implementation for backward compatibility
class OCamlPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for OCaml language chunking."""

    @property
    def language_name(self) -> str:
        return "ocaml"

    @property
    def supported_extensions(self) -> set[str]:
        return {".ml", ".mli", ".mll", ".mly"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "value_definition",
            "let_binding",
            "let_rec_binding",
            "function_definition",
            "fun_expression",
            "type_definition",
            "type_binding",
            "module_definition",
            "module_binding",
            "signature",
            "structure",
            "exception_definition",
            "class_definition",
            "class_binding",
            "comment",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from an OCaml node."""
        if node.type in {"value_definition", "let_binding", "let_rec_binding"}:
            # Look for the identifier in the binding
            for child in node.children:
                if child.type == "value_name":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                if child.type == "let_binding":
                    # Recursive case for let rec
                    for subchild in child.children:
                        if subchild.type == "value_name":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif node.type in {"type_definition", "type_binding"}:
            # Look for type name
            for child in node.children:
                if child.type in {"type_constructor", "lowercase_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type in {"module_definition", "module_binding"}:
            # Look for module name
            for child in node.children:
                if child.type in {"module_name", "uppercase_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type == "exception_definition":
            # Look for exception name
            for child in node.children:
                if child.type in {"constructor_name", "uppercase_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type in {"class_definition", "class_binding"}:
            # Look for class name
            for child in node.children:
                if child.type in {"class_name", "lowercase_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to OCaml."""
        chunks = []

        def extract_chunks(n: Node, module_context: str | None = None):
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
                if n.type in {"let_binding", "let_rec_binding"}:
                    chunk["is_recursive"] = n.type == "let_rec_binding"
                elif n.type == "type_definition":
                    # Check if it's a variant type, record, or alias
                    if "=" in content and "|" in content:
                        chunk["type_kind"] = "variant"
                    elif "=" in content and "{" in content:
                        chunk["type_kind"] = "record"
                    else:
                        chunk["type_kind"] = "alias"

                chunks.append(chunk)

                # Update module context for children
                if n.type in {"module_definition", "module_binding"}:
                    module_context = self.get_node_name(n, source)

            for child in n.children:
                extract_chunks(child, module_context)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get OCaml-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All definition and binding nodes
        if node.type.endswith("_definition") or node.type.endswith("_binding"):
            return True
        # Functions and expressions
        if node.type in {"fun_expression", "function_expression"}:
            return True
        # Module components
        if node.type in {"signature", "structure"}:
            return True
        # Comments
        return node.type == "comment"

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type in {"value_definition", "let_binding"}:
            if name:
                return f"let {name}"
            return "let binding"
        if node.type == "let_rec_binding":
            if name:
                return f"let rec {name}"
            return "let rec binding"
        if node.type in {"type_definition", "type_binding"}:
            if name:
                return f"type {name}"
            return "type definition"
        if node.type in {"module_definition", "module_binding"}:
            if name:
                return f"module {name}"
            return "module"
        if node.type == "exception_definition":
            if name:
                return f"exception {name}"
            return "exception"
        if node.type in {"class_definition", "class_binding"}:
            if name:
                return f"class {name}"
            return "class"
        if node.type == "signature":
            return "module signature"
        if node.type == "structure":
            return "module structure"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process OCaml nodes with special handling for nested structures."""
        # Handle module definitions with signatures
        if node.type in {"module_definition", "module_binding"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Set module name as context for children
                module_name = self.get_node_name(node, source)
                if module_name:
                    parent_context = f"module:{module_name}"
                return chunk

        # Handle let rec with multiple bindings
        if node.type == "let_rec_binding":
            # Each binding in a let rec can be a separate chunk
            chunks = []
            main_chunk = self.create_chunk(node, source, file_path, parent_context)
            if main_chunk and self.should_include_chunk(main_chunk):
                chunks.append(main_chunk)

            # Look for individual function bindings within let rec
            for child in node.children:
                if child.type == "let_binding":
                    sub_chunk = self.create_chunk(
                        child,
                        source,
                        file_path,
                        parent_context,
                    )
                    if sub_chunk and self.should_include_chunk(sub_chunk):
                        sub_chunk.node_type = "recursive_function"
                        chunks.append(sub_chunk)

            return chunks if chunks else None

        # Handle type definitions with variants
        if node.type == "type_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                # Check type kind
                content = source[node.start_byte : node.end_byte].decode("utf-8")
                if "|" in content:
                    chunk.metadata = {"type_kind": "variant"}
                elif "{" in content and "}" in content:
                    chunk.metadata = {"type_kind": "record"}
                return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        # For modules, pass the module name to children
        if node.type in {"module_definition", "module_binding"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"module:{name}"

        # For classes, pass class info
        if node.type in {"class_definition", "class_binding"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"class:{name}"

        return chunk.node_type
