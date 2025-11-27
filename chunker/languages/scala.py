"""
Support for Scala language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode_bytes

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class ScalaConfig(LanguageConfig):
    """Language configuration for Scala."""

    @property
    def language_id(self) -> str:
        return "scala"

    @property
    def chunk_types(self) -> set[str]:
        """Scala-specific chunk types."""
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
            "package_clause",
            "import_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".scala", ".sc"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"match_expression", "case_clause"},
                include_children=True,
                priority=5,
                metadata={"type": "pattern_matching"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"implicit_definition"},
                include_children=False,
                priority=6,
                metadata={"type": "implicit"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("number")

    def should_chunk_node(self, node_type: str) -> bool:
        """Override to handle all chunk types including case classes."""
        return node_type in self.chunk_types

    def _is_case_class(self, node) -> bool:
        """Check if a class_definition node is a case class."""
        if node.type != "class_definition":
            return False

        # Case classes have 'case' as their first child
        if node.children and node.children[0].type == "case":
            return True

        return False


# Register the Scala configuration
from .base import language_config_registry

scala_config = ScalaConfig()
language_config_registry.register(scala_config, aliases=["scala"])


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
            "class_definition",
            "object_definition",
            "trait_definition",
            "case_class_definition",
            "val_definition",
            "var_definition",
            "type_definition",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Scala node."""
        if node.type in {
            "function_definition",
            "method_definition",
            "val_definition",
            "var_definition",
        }:
            for child in node.children:
                if child.type == "identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type in {
            "class_definition",
            "object_definition",
            "trait_definition",
            "case_class_definition",
        }:
            for child in node.children:
                if child.type in {"identifier", "class_identifier"}:
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type == "type_definition":
            for child in node.children:
                if child.type == "type_identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Scala."""
        chunks = []

        def extract_chunks(n: Node, parent_type: str | None = None):
            # Check if this is a case class and adjust type accordingly
            node_type = n.type
            if n.type == "class_definition" and self._is_case_class(n):
                node_type = "case_class_definition"

            if node_type in self.default_chunk_types:
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])
                chunk = {
                    "type": node_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if node_type in {"function_definition", "method_definition"}:
                    chunk["is_method"] = True
                    if "private" in content[:50]:
                        chunk["visibility"] = "private"
                    elif "protected" in content[:50]:
                        chunk["visibility"] = "protected"
                    else:
                        chunk["visibility"] = "public"
                elif node_type == "case_class_definition":
                    chunk["is_case_class"] = True
                elif node_type == "object_definition":
                    chunk["is_singleton"] = True
                elif node_type in {"val_definition", "var_definition"}:
                    chunk["is_field"] = True
                    chunk["is_mutable"] = node_type == "var_definition"
                chunks.append(chunk)
            new_parent = (
                node_type
                if node_type
                in {
                    "class_definition",
                    "case_class_definition",
                    "object_definition",
                    "trait_definition",
                }
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
        if node.type in self.default_chunk_types:
            return True
        if node.type == "implicit_definition":
            return True
        if node.type == "match_expression":
            return len(node.children) > 3
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format (prefix, default)
        node_context_map = {
            "function_definition": ("def", "method"),
            "method_definition": ("def", "method"),
            "class_definition": ("class", "class"),
            "case_class_definition": ("case class", "case class"),
            "object_definition": ("object", "object"),
            "trait_definition": ("trait", "trait"),
            "val_definition": ("val", "value"),
            "var_definition": ("var", "variable"),
            "type_definition": ("type", "type alias"),
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
        """Process Scala nodes with special handling for complex constructs."""
        # Handle case class definitions
        if node.type == "class_definition" and self._is_case_class(node):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "case_class_definition"
                return chunk if self.should_include_chunk(chunk) else None

        if node.type == "object_definition" and self._is_companion_object(node, source):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                chunk.node_type = "companion_object"
                return chunk if self.should_include_chunk(chunk) else None
        if node.type in {"val_definition", "function_definition"}:
            content = safe_decode_bytes(source[node.start_byte : node.end_byte])
            if "implicit" in content[:50]:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = f"implicit_{node.type}"
                    return chunk if self.should_include_chunk(chunk) else None
        if node.type == "for_expression" and any(
            child.type == "generator" for child in node.children
        ):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.node_type = "for_comprehension"
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def _is_companion_object(self, node: Node, source: bytes) -> bool:
        """Check if an object is a companion object to a class."""
        parent = node.parent
        if not parent:
            return False

        obj_name = self.get_node_name(node, source)
        if not obj_name:
            return False

        for sibling in parent.children:
            if self._is_matching_class(sibling, node, obj_name, source):
                return True
        return False

    def _is_matching_class(
        self,
        sibling: Node,
        object_node: Node,
        obj_name: str,
        source: bytes,
    ) -> bool:
        """Check if sibling is a class matching the object name."""
        if sibling == object_node:
            return False

        if sibling.type not in {"class_definition", "case_class_definition"}:
            return False

        class_name = self.get_node_name(sibling, source)
        return class_name == obj_name

    def _is_case_class(self, node: Node) -> bool:
        """Check if a class_definition node is a case class."""
        if node.type != "class_definition":
            return False

        # Case classes have 'case' as their first child
        if node.children and node.children[0].type == "case":
            return True

        return False
