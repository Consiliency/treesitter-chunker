"""
Support for MATLAB language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.types import CodeChunk

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class MATLABConfig(LanguageConfig):
    """Language configuration for MATLAB."""

    @property
    def language_id(self) -> str:
        return "matlab"

    @property
    def chunk_types(self) -> set[str]:
        """MATLAB-specific chunk types."""
        return {
            "function_definition",
            "function_declaration",
            "class_definition",  # Full class definition node
            "classdef",  # Alternative form used by tree-sitter-matlab
            # Note: methods, properties, events, enumeration are child blocks of class_definition
            "methods",
            "method_definition",
            "properties",
            "events",
            "enumeration",
            "script",
            "comment",
            "lambda",  # anonymous functions
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".m"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"nested_function", "local_function"},
                include_children=True,
                priority=5,
                metadata={"type": "nested_function"},
            ),
        )
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        # For the language configuration system, ignore keyword tokens that duplicate their blocks
        # Note: The plugin system handles these differently and still supports them
        # Note: classdef is explicitly included in chunk_types for class detection
        self.add_ignore_type("function")  # keyword inside function_definition
        # Note: properties, methods, events, enumeration have same issue but are needed as chunks


# Register the MATLAB configuration
from .base import language_config_registry

# Register the configuration so it's available to the core chunking system
language_config_registry.register(MATLABConfig())


class MATLABPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for MATLAB language chunking."""

    @property
    def language_name(self) -> str:
        return "matlab"

    @property
    def supported_extensions(self) -> set[str]:
        return {".m", ".mlx"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_definition",
            "function_declaration",
            "classdef",
            "class_definition",
            "methods",
            "method_definition",
            "properties",
            "events",
            "enumeration",
            "script",
            "comment",
            "lambda",  # anonymous functions
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a MATLAB node."""
        if node.type in {"function_definition", "function_declaration"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                if child.type == "function_output":
                    for subchild in (
                        child.next_sibling.children if child.next_sibling else []
                    ):
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif (
            node.type in {"classdef", "class_definition"}
            or node.type == "method_definition"
        ):
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        elif node.type == "lambda":
            # For anonymous functions, return a descriptive name
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            # Extract the parameter part if possible
            if "@(" in content:
                param_end = content.find(")")
                if param_end > 0:
                    params = content[2:param_end]  # Skip "@("
                    return f"lambda({params})"
            return "lambda"
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to MATLAB."""
        chunks = []

        def extract_chunks(n: Node, class_context: str | None = None):
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
                if class_context and n.type in {"method_definition", "methods"}:
                    chunk["class_context"] = class_context
                chunks.append(chunk)
                if n.type in {"classdef", "class_definition"}:
                    class_context = self.get_node_name(n, source)
            for child in n.children:
                extract_chunks(child, class_context)

        # First extract explicit chunks (functions, classes, etc.)
        extract_chunks(node)

        # If this is a source_file node, check if it should be treated as a script
        if node.type == "source_file":
            # Check if there are top-level statements that aren't functions/classes
            has_top_level_code = False
            has_functions_or_classes = False

            for child in node.children:
                if child.type in {
                    "function_definition",
                    "classdef",
                    "class_definition",
                }:
                    has_functions_or_classes = True
                elif child.type in {
                    "assignment",
                    "function_call",
                    "command",
                    "comment",
                }:
                    has_top_level_code = True

            # If there's top-level code (and optionally functions/classes), treat as script
            if has_top_level_code:
                content = source.decode("utf-8", errors="replace")
                script_chunk = {
                    "type": "script",
                    "start_line": 1,
                    "end_line": content.count("\n") + 1,
                    "content": content,
                    "name": None,
                }
                chunks.append(script_chunk)

        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get MATLAB-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in {
            "function_definition",
            "function_declaration",
            "classdef",
            "class_definition",
        }:
            return True
        if node.type in {
            "methods",
            "properties",
            "events",
            "enumeration",
        }:
            return True
        return node.type in {"script", "comment", "lambda"}

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format (prefix, default, needs_name)
        node_context_map = {
            "function_definition": ("function", "function", True),
            "function_declaration": ("function", "function", True),
            "classdef": ("classdef", "classdef", True),
            "class_definition": ("classdef", "classdef", True),
            "methods": (None, "methods block", False),
            "properties": (None, "properties block", False),
            "events": (None, "events block", False),
            "enumeration": (None, "enumeration block", False),
            "method_definition": ("method", "method", True),
            "script": (None, "script", False),
            "comment": (None, "comment", False),
            "lambda": ("lambda", "lambda", True),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        prefix, default, needs_name = context_info
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
        """Process MATLAB nodes with special handling for class structure."""
        if node.type in {"classdef", "class_definition"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                class_name = self.get_node_name(node, source)
                if class_name:
                    parent_context = f"class:{class_name}"
                return chunk
        if (
            node.type in {"methods", "properties", "events", "enumeration"}
            and parent_context
        ):
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                if parent_context.startswith("class:"):
                    chunk.parent_context = parent_context
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        if node.type in {"classdef", "class_definition"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"class:{name}"
        if node.type in {"methods"} and chunk.parent_context:
            return chunk.parent_context
        return chunk.node_type

    def walk_tree(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> list[CodeChunk]:
        """
        Override tree walking to handle MATLAB script detection.
        """
        chunks: list[CodeChunk] = []

        # If this is the root source_file, check for script pattern
        if node.type == "source_file" and parent_context is None:
            # Check if there are top-level statements that make this a script
            has_top_level_code = False

            for child in node.children:
                if child.type in {"assignment", "function_call", "command", "comment"}:
                    has_top_level_code = True
                    break

            # If it's a script, create a script chunk for the whole file
            if has_top_level_code:
                content = source.decode("utf-8", errors="replace")
                script_chunk = CodeChunk(
                    language=self.language_name,
                    file_path=file_path,
                    node_type="script",
                    start_line=1,
                    end_line=content.count("\n") + 1,
                    byte_start=0,
                    byte_end=len(source),
                    parent_context="",
                    content=content,
                )
                chunks.append(script_chunk)

        # Process regular nodes
        chunk = self.process_node(node, source, file_path, parent_context)
        if chunk:
            chunks.append(chunk)
            parent_context = self.get_context_for_children(node, chunk)

        # Recursively process children
        for child in node.children:
            chunks.extend(self.walk_tree(child, source, file_path, parent_context))

        return chunks
