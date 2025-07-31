"""
Support for Dart language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

class DartConfig(LanguageConfig):
    """Language configuration for Dart."""

    @property
    def language_id(self) -> str:
        return "dart"

    @property
    def chunk_types(self) -> set[str]:
        """Dart-specific chunk types."""
        return {
            # Functions and methods
            "function_declaration",
            "method_declaration",
            "getter_declaration",
            "setter_declaration",
            "constructor_declaration",
            # Classes and mixins
            "class_declaration",
            "mixin_declaration",
            "extension_declaration",
            "enum_declaration",
            # Other declarations
            "variable_declaration",
            "field_declaration",
            "typedef_declaration",
            "import_directive",
            "export_directive",
            "part_directive",
            "library_directive",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".dart"}

    def __init__(self):
        super().__init__()

        # Add rules for async functions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"async_function", "async_method"},
                include_children=False,
                priority=6,
                metadata={"type": "async"},
            ),
        )

        # Add rules for factory constructors
        self.add_chunk_rule(
            ChunkRule(
                node_types={"factory_constructor"},
                include_children=False,
                priority=5,
                metadata={"type": "factory"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("string_literal")
        self.add_ignore_type("number_literal")

# Register the Dart configuration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

# Plugin implementation for backward compatibility
class DartPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Dart language chunking."""

    @property
    def language_name(self) -> str:
        return "dart"

    @property
    def supported_extensions(self) -> set[str]:
        return {".dart"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "method_declaration",
            "getter_declaration",
            "setter_declaration",
            "constructor_declaration",
            "class_declaration",
            "mixin_declaration",
            "extension_declaration",
            "enum_declaration",
            "variable_declaration",
            "field_declaration",
            "typedef_declaration",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Dart node."""
        # For functions and methods
        if node.type in {
            "function_declaration",
            "method_declaration",
            "getter_declaration",
            "setter_declaration",
        }:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        # For constructors
        elif node.type == "constructor_declaration":
            # Constructor might have class name or be named
            for child in node.children:
                if child.type in {"identifier", "constructor_name"}:
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        # For classes, mixins, extensions
        elif (
            node.type
            in {
                "class_declaration",
                "mixin_declaration",
                "extension_declaration",
                "enum_declaration",
            }
            or node.type == "typedef_declaration"
        ):
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Dart."""
        chunks = []

        def extract_chunks(n: Node, parent_class: str | None = None):
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
                if n.type in {"function_declaration", "method_declaration"}:
                    chunk["is_method"] = n.type == "method_declaration"
                    # Check for async
                    if "async" in content[:50]:
                        chunk["is_async"] = True
                    # Check for static
                    if "static" in content[:50]:
                        chunk["is_static"] = True
                    # Check visibility
                    if (
                        content.strip().startswith("_")
                        or "_" in (chunk.get("name", "") or "")[:1]
                    ):
                        chunk["visibility"] = "private"
                    else:
                        chunk["visibility"] = "public"
                elif n.type in {"getter_declaration", "setter_declaration"}:
                    chunk["is_property"] = True
                    chunk["property_type"] = (
                        "getter" if n.type == "getter_declaration" else "setter"
                    )
                elif n.type == "constructor_declaration":
                    chunk["is_constructor"] = True
                    if "factory" in content[:50]:
                        chunk["constructor_type"] = "factory"
                    else:
                        chunk["constructor_type"] = "regular"
                elif n.type == "class_declaration":
                    chunk["is_class"] = True
                    if "abstract" in content[:50]:
                        chunk["is_abstract"] = True
                elif n.type == "mixin_declaration":
                    chunk["is_mixin"] = True
                elif n.type == "extension_declaration":
                    chunk["is_extension"] = True

                if parent_class:
                    chunk["parent_class"] = parent_class

                chunks.append(chunk)

            # Track class context
            class_name = parent_class
            if n.type == "class_declaration":
                class_name = self.get_node_name(n, source)

            for child in n.children:
                extract_chunks(child, class_name)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Dart-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All main declaration types should be chunked
        if node.type in self.default_chunk_types:
            return True
        # Widget build methods are important in Flutter
        if node.type == "method_declaration":
            name = self.get_node_name(node, None)
            if name == "build":
                return True
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type == "function_declaration":
            return f"function {name}" if name else "function"
        if node.type == "method_declaration":
            return f"method {name}" if name else "method"
        if node.type == "getter_declaration":
            return f"get {name}" if name else "getter"
        if node.type == "setter_declaration":
            return f"set {name}" if name else "setter"
        if node.type == "constructor_declaration":
            return f"constructor {name}" if name else "constructor"
        if node.type == "class_declaration":
            return f"class {name}" if name else "class"
        if node.type == "mixin_declaration":
            return f"mixin {name}" if name else "mixin"
        if node.type == "extension_declaration":
            return f"extension {name}" if name else "extension"
        if node.type == "enum_declaration":
            return f"enum {name}" if name else "enum"
        if node.type == "typedef_declaration":
            return f"typedef {name}" if name else "typedef"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Dart nodes with special handling for Flutter widgets."""
        # Handle Flutter widget classes specially
        if node.type == "class_declaration":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            # Check if it extends StatelessWidget or StatefulWidget
            if (
                "extends StatelessWidget" in content
                or "extends StatefulWidget" in content
            ):
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = "widget_class"
                    chunk.metadata = {"is_flutter_widget": True}
                    if "StatefulWidget" in content:
                        chunk.metadata["widget_type"] = "stateful"
                    else:
                        chunk.metadata["widget_type"] = "stateless"
                    return chunk if self.should_include_chunk(chunk) else None

        # Handle async functions
        if node.type in {"function_declaration", "method_declaration"}:
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "async" in content[:100]:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.metadata = {"is_async": True}
                    # Check for generators
                    if "async*" in content[:100]:
                        chunk.metadata["is_generator"] = True
                    return chunk if self.should_include_chunk(chunk) else None

        # Handle factory constructors
        if node.type == "constructor_declaration":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "factory" in content[:50]:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = "factory_constructor"
                    return chunk if self.should_include_chunk(chunk) else None

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
