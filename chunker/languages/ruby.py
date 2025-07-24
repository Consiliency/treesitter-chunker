"""Ruby language support for chunking."""

from tree_sitter import Node

from ..types import CodeChunk
from .base import LanguageChunker


class RubyChunker(LanguageChunker):
    """Chunker implementation for Ruby."""

    @property
    def language_name(self) -> str:
        """Get the language name."""
        return "ruby"

    @property
    def file_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".rb", ".rake", ".gemspec", ".ru"]

    def get_chunk_node_types(self) -> set[str]:
        """Get node types that should be chunked."""
        return {
            # Methods and functions
            "method",
            "singleton_method",
            # Classes and modules
            "class",
            "module",
            "singleton_class",
            # Blocks and lambdas (selectively)
            "block",
            "lambda",
            # Constants
            "assignment",  # When assigning to constants
            # Attribute accessors
            "call",  # When it's attr_accessor, attr_reader, attr_writer
        }

    def get_scope_node_types(self) -> set[str]:
        """Get node types that define scopes."""
        return {
            "program",
            "class",
            "module",
            "method",
            "singleton_method",
            "block",
            "lambda",
            "if",
            "unless",
            "case",
            "while",
            "until",
            "for",
            "begin",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False

        # Special handling for blocks - only chunk significant ones
        if node.type == "block":
            # Check if it's a DSL block (like RSpec, Rails routes, etc.)
            parent = node.parent
            if parent and parent.type == "call":
                method_name = self._get_call_method_name(parent)
                if method_name in [
                    "describe",
                    "context",
                    "it",
                    "before",
                    "after",
                    "namespace",
                    "resources",
                    "scope",
                    "task",
                ]:
                    return True
            return False

        # Special handling for calls - only chunk attr_* methods
        if node.type == "call":
            method_name = self._get_call_method_name(node)
            return method_name in ["attr_accessor", "attr_reader", "attr_writer"]

        # Skip anonymous methods/lambdas
        if node.type in ["method", "lambda"] and not self._has_name(node):
            return False

        return True

    def extract_chunk_info(self, node: Node, source_code: bytes) -> dict:
        """Extract additional information for a chunk."""
        info = {}

        if node.type == "method":
            # Extract method name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["method_name"] = name_node.text.decode("utf-8")

            # Check for visibility
            info["visibility"] = self._get_method_visibility(node)

        elif node.type == "class":
            # Extract class name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["class_name"] = name_node.text.decode("utf-8")

            # Extract superclass
            superclass_node = node.child_by_field_name("superclass")
            if superclass_node:
                info["superclass"] = superclass_node.text.decode("utf-8")

        elif node.type == "module":
            # Extract module name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["module_name"] = name_node.text.decode("utf-8")

        elif node.type == "call":
            # For attr_* calls, extract attribute names
            method_name = self._get_call_method_name(node)
            if method_name in ["attr_accessor", "attr_reader", "attr_writer"]:
                info["attr_type"] = method_name
                info["attributes"] = self._extract_attr_names(node)

        elif node.type == "block":
            # For DSL blocks, extract the block type
            parent = node.parent
            if parent and parent.type == "call":
                method_name = self._get_call_method_name(parent)
                info["block_type"] = method_name

                # Extract block parameter (e.g., describe "User" do)
                args = self._get_call_arguments(parent)
                if args:
                    info["block_description"] = args[0]

        return info

    def get_context_nodes(self, node: Node) -> list[Node]:
        """Get nodes that provide context for a chunk."""
        context_nodes = []

        # Walk up to find containing class/module
        current = node.parent
        while current:
            if current.type in ["class", "module"]:
                context_nodes.append(current)
                # Continue to find nested classes/modules
            elif current.type == "program":
                break
            current = current.parent

        return context_nodes

    def _has_name(self, node: Node) -> bool:
        """Check if a node has a name."""
        if node.type == "method":
            name_node = node.child_by_field_name("name")
            return name_node is not None
        if node.type == "lambda":
            # Lambdas are usually anonymous
            return False
        return True

    def _get_call_method_name(self, call_node: Node) -> str | None:
        """Extract method name from a call node."""
        method_node = call_node.child_by_field_name("method")
        if method_node:
            return method_node.text.decode("utf-8")
        return None

    def _get_call_arguments(self, call_node: Node) -> list[str]:
        """Extract arguments from a call node."""
        args = []
        arguments_node = call_node.child_by_field_name("arguments")
        if arguments_node:
            for child in arguments_node.children:
                if child.type in ["string", "symbol", "identifier"]:
                    args.append(child.text.decode("utf-8").strip("\"'"))
        return args

    def _extract_attr_names(self, attr_call_node: Node) -> list[str]:
        """Extract attribute names from attr_* calls."""
        names = []
        arguments_node = attr_call_node.child_by_field_name("arguments")
        if arguments_node:
            for child in arguments_node.children:
                if child.type == "symbol":
                    # Remove the : prefix from symbols
                    name = child.text.decode("utf-8").lstrip(":")
                    names.append(name)
        return names

    def _get_method_visibility(self, method_node: Node) -> str:
        """Determine method visibility (public/private/protected)."""
        # Look for visibility modifiers before this method
        if not method_node.parent:
            return "public"

        # Check previous siblings for visibility keywords
        prev = method_node.prev_sibling
        while prev:
            if prev.type == "call":
                method_name = self._get_call_method_name(prev)
                if method_name in ["private", "protected", "public"]:
                    return method_name
            prev = prev.prev_sibling

        return "public"  # Default visibility

    def merge_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks."""
        merged = []

        # Group attr_* declarations in the same class
        attr_groups = {}
        other_chunks = []

        for chunk in chunks:
            if chunk.metadata.get("attr_type"):
                # Find parent class context
                parent_class = chunk.parent_context
                if parent_class:
                    key = (parent_class, chunk.metadata["attr_type"])
                    if key not in attr_groups:
                        attr_groups[key] = []
                    attr_groups[key].append(chunk)
                else:
                    other_chunks.append(chunk)
            else:
                other_chunks.append(chunk)

        # Merge attr_* groups
        for (parent_class, attr_type), attr_chunks in attr_groups.items():
            if len(attr_chunks) > 1:
                # Merge into a single chunk
                all_attrs = []
                for chunk in attr_chunks:
                    all_attrs.extend(chunk.metadata.get("attributes", []))

                # Use the first chunk as template
                merged_chunk = attr_chunks[0]
                merged_chunk.metadata["attributes"] = all_attrs
                merged_chunk.content = (
                    f"{attr_type} {', '.join(':' + a for a in all_attrs)}"
                )
                merged.append(merged_chunk)
            else:
                merged.extend(attr_chunks)

        merged.extend(other_chunks)
        return merged
