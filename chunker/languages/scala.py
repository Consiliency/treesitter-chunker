"""
Support for Scala language.
"""

from __future__ import annotations
from tree_sitter import Node

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class ScalaConfig(LanguageConfig):
    """Language configuration for Scala."""

    @property
    def language_id(self) -> str:
        return "scala"

    @property
    def chunk_types(self) -> set[str]:
        """Scala-specific chunk types."""
        return {
            # Functions and methods
            "function_definition",
            "function_declaration",
            "method_definition",
            "method_declaration",
            # Classes and objects
            "class_definition",
            "object_definition",
            "trait_definition",
            "case_class_definition",
            # Other declarations
            "val_definition",
            "var_definition",
            "type_definition",
            "package_clause",
            "import_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".scala", ".sc"}

    def __init__(self):
        super().__init__()

        # Add rules for pattern matching
        self.add_chunk_rule(
            ChunkRule(
                node_types={"match_expression", "case_clause"},
                include_children=True,
                priority=5,
                metadata={"type": "pattern_matching"},
            ),
        )

        # Add rules for implicit definitions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"implicit_definition"},
                include_children=False,
                priority=6,
                metadata={"type": "implicit"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("number")


# Register the Scala configuration
from typing import TYPE_CHECKING

from . import language_config_registry

if TYPE_CHECKING:

language_config_registry.register(ScalaConfig(), aliases=["sc"])


# Plugin implementation for backward compatibility
class ScalaPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Scala language chunking."""

    @property
    def language_name(self) -> str:
        return "scala"

    @property
    def supported_extensions(self) -> set[str]:
        return {".scala", ".sc"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "function_declaration",
            "method_definition",
            "method_declaration",
            "class_definition",
            "object_definition",
            "trait_definition",
            "case_class_definition",
            "val_definition",
            "var_definition",
            "type_definition",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Scala node."""
        # For functions and methods
        if node.type in {
            "function_definition",
            "method_definition",
            "val_definition",
            "var_definition",
        }:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        # For classes, objects, and traits
        elif node.type in {
            "class_definition",
            "object_definition",
            "trait_definition",
            "case_class_definition",
        }:
            for child in node.children:
                if child.type in {"identifier", "class_identifier"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        # For type definitions
        elif node.type == "type_definition":
            for child in node.children:
                if child.type == "type_identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Scala."""
        chunks = []

        def extract_chunks(n: Node, parent_type: str | None = None):
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

                # Add metadata for different types
                if n.type in {"function_definition", "method_definition"}:
                    chunk["is_method"] = True
                    # Check for access modifiers
                    if "private" in content[:50]:
                        chunk["visibility"] = "private"
                    elif "protected" in content[:50]:
                        chunk["visibility"] = "protected"
                    else:
                        chunk["visibility"] = "public"
                elif n.type == "case_class_definition":
                    chunk["is_case_class"] = True
                elif n.type == "object_definition":
                    chunk["is_singleton"] = True
                elif n.type in {"val_definition", "var_definition"}:
                    chunk["is_field"] = True
                    chunk["is_mutable"] = n.type == "var_definition"

                chunks.append(chunk)

            # Track context
            new_parent = (
                n.type
                if n.type
                in {"class_definition", "object_definition", "trait_definition"}
                else parent_type
            )
            for child in n.children:
                extract_chunks(child, new_parent)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Scala-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All main declaration types should be chunked
        if node.type in self.default_chunk_types:
            return True
        # Special handling for implicit definitions
        if node.type == "implicit_definition":
            return True
        # Pattern matching blocks
        if node.type == "match_expression":
            # Only chunk if complex enough
            return len(node.children) > 3
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type in {"function_definition", "method_definition"}:
            return f"def {name}" if name else "method"
        if node.type == "class_definition":
            return f"class {name}" if name else "class"
        if node.type == "case_class_definition":
            return f"case class {name}" if name else "case class"
        if node.type == "object_definition":
            return f"object {name}" if name else "object"
        if node.type == "trait_definition":
            return f"trait {name}" if name else "trait"
        if node.type == "val_definition":
            return f"val {name}" if name else "value"
        if node.type == "var_definition":
            return f"var {name}" if name else "variable"
        if node.type == "type_definition":
            return f"type {name}" if name else "type alias"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Scala nodes with special handling for complex constructs."""
        # Handle companion objects
        if node.type == "object_definition":
            # Check if this is a companion object
            parent = node.parent
            if parent:
                # Look for adjacent class with same name
                obj_name = self.get_node_name(node, source)
                for sibling in parent.children:
                    if (
                        sibling.type in {"class_definition", "case_class_definition"}
                        and sibling != node
                    ):
                        class_name = self.get_node_name(sibling, source)
                        if obj_name == class_name:
                            chunk = self.create_chunk(
                                node,
                                source,
                                file_path,
                                parent_context,
                            )
                            if chunk:
                                chunk.node_type = "companion_object"
                                return (
                                    chunk if self.should_include_chunk(chunk) else None
                                )

        # Handle implicit conversions
        if node.type in {"val_definition", "function_definition"}:
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "implicit" in content[:50]:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = f"implicit_{node.type}"
                    return chunk if self.should_include_chunk(chunk) else None

        # Handle for comprehensions
        if node.type == "for_expression":
            # Check if it's a complex for comprehension
            if any(child.type == "generator" for child in node.children):
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk and self.should_include_chunk(chunk):
                    chunk.node_type = "for_comprehension"
                    return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
