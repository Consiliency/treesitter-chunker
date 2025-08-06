"""
Support for R language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class RConfig(LanguageConfig):
    """Language configuration for R."""

    @property
    def language_id(self) -> str:
        return "r"

    @property
    def chunk_types(self) -> set[str]:
        """R-specific chunk types."""
        return {
            "function_definition",
            "function_declaration",
            "assignment",
            "left_assignment",
            "right_assignment",
            "if_statement",
            "for_statement",
            "while_statement",
            "repeat_statement",
            "s3_method",
            "s4_method",
            "setClass",
            "setMethod",
            "comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".r", ".R", ".rmd", ".Rmd"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"assignment", "left_assignment"},
                include_children=True,
                priority=5,
                metadata={"type": "function_assignment"},
            ),
        )
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("identifier")

    @staticmethod
    def _is_function_assignment(node: Node, _source: bytes) -> bool:
        """Check if an assignment is a function assignment."""
        return any(child.type == "function_definition" for child in node.children)


# Register the R configuration


# Plugin implementation for backward compatibility


class RPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for R language chunking."""

    @property
    def language_name(self) -> str:
        return "r"

    @property
    def supported_extensions(self) -> set[str]:
        return {".r", ".R", ".rmd", ".Rmd"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "function_declaration",
            "assignment",
            "left_assignment",
            "right_assignment",
            "if_statement",
            "for_statement",
            "while_statement",
            "repeat_statement",
            "comment",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from an R node."""
        if node.type in {"assignment", "left_assignment"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                break
        elif node.type == "function_definition":
            parent = node.parent
            if parent and parent.type in {"assignment", "left_assignment"}:
                for child in parent.children:
                    if child.type == "identifier":
                        return source[child.start_byte : child.end_byte].decode("utf-8")
                    break
        elif node.type in {"if_statement", "for_statement", "while_statement"}:
            return node.type.replace("_statement", "")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to R."""
        chunks = []

        def extract_chunks(n: Node, _parent_type: str | None = None):
            if n.type in self.default_chunk_types:
                if n.type in {"assignment", "left_assignment"}:
                    is_function = False
                    for child in n.children:
                        if child.type == "function_definition":
                            is_function = True
                            break
                    if not is_function and n.type not in {
                        "if_statement",
                        "for_statement",
                        "while_statement",
                    }:
                        return
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
                if n.type in {"assignment", "left_assignment"}:
                    for child in n.children:
                        if child.type == "function_definition":
                            chunk["is_function"] = True
                            break
                chunks.append(chunk)
            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get R-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type == "function_definition":
            return True
        if node.type in {"assignment", "left_assignment"}:
            for child in node.children:
                if child.type == "function_definition":
                    return True
        if node.type in {
            "if_statement",
            "for_statement",
            "while_statement",
            "repeat_statement",
        }:
            return True
        return node.type == "comment"

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Handle assignments specially
        if node.type in {"assignment", "left_assignment"}:
            return self._get_assignment_context(node, source)

        # Handle function definitions
        if node.type == "function_definition":
            return self._get_function_context(node, source)

        # Map control structures
        control_context_map = {
            "if_statement": "if statement",
            "for_statement": "for loop",
            "while_statement": "while loop",
            "repeat_statement": "repeat loop",
        }

        return control_context_map.get(node.type)

    def _get_assignment_context(self, node: Node, source: bytes) -> str | None:
        """Get context for assignment nodes."""
        name = self.get_node_name(node, source)
        if not name:
            return None

        for child in node.children:
            if child.type == "function_definition":
                return f"function {name}"
        return f"assignment {name}"

    def _get_function_context(self, node: Node, source: bytes) -> str:
        """Get context for function definition nodes."""
        if node.parent and node.parent.type in {"assignment", "left_assignment"}:
            parent_name = self.get_node_name(node.parent, source)
            if parent_name:
                return f"function {parent_name}"
        return "anonymous function"

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process R nodes with special handling for function assignments."""
        if node.type in {"assignment", "left_assignment"}:
            is_function_assignment = False
            for child in node.children:
                if child.type == "function_definition":
                    is_function_assignment = True
                    break
            if is_function_assignment:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk and self.should_include_chunk(chunk):
                    chunk.node_type = "function_assignment"
                    return chunk
            else:
                return None
        if node.type in {
            "if_statement",
            "for_statement",
            "while_statement",
            "repeat_statement",
        }:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        if node.type in {
            "if_statement",
            "for_statement",
            "while_statement",
            "repeat_statement",
        }:
            return node.type
        if (
            hasattr(
                chunk,
                "node_type",
            )
            and chunk.node_type == "function_assignment"
        ):
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"function:{name}"
        return chunk.node_type
