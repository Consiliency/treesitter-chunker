"""Go language support for chunking."""

from tree_sitter import Node

from chunker.types import CodeChunk

from .base import LanguageChunker


class GoChunker(LanguageChunker):
    """Chunker implementation for Go."""

    @property
    def language_name(self) -> str:
        """Get the language name."""
        return "go"

    @property
    def file_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".go"]

    def get_chunk_node_types(self) -> set[str]:
        """Get node types that should be chunked."""
        return {
            # Functions and methods
            "function_declaration",
            "method_declaration",
            # Types
            "type_declaration",
            "type_spec",
            # Interfaces
            "interface_type",
            # Structs
            "struct_type",
            # Constants and variables
            "const_declaration",
            "var_declaration",
            # Packages (for context)
            "package_clause",
        }

    def get_scope_node_types(self) -> set[str]:
        """Get node types that define scopes."""
        return {
            "source_file",
            "function_declaration",
            "method_declaration",
            "block",
            "if_statement",
            "for_statement",
            "switch_statement",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False

        # Skip anonymous functions
        if node.type == "function_declaration" and not self._has_name(node):
            return False

        # Skip single-line type aliases
        if node.type == "type_spec":
            # Only chunk complex types (structs, interfaces)
            for child in node.children:
                if child.type in ["struct_type", "interface_type"]:
                    return True
            return False

        return True

    def extract_chunk_info(self, node: Node, _source_code: bytes) -> dict:
        """Extract additional information for a chunk."""
        info = {}

        if node.type == "function_declaration":
            # Extract function name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["function_name"] = name_node.text.decode("utf-8")

            # Extract receiver for methods
            params_node = node.child_by_field_name("parameters")
            if params_node and params_node.child_count > 0:
                first_param = params_node.children[0]
                if first_param.type == "parameter_declaration":
                    # Check if it's a method receiver
                    type_node = first_param.child_by_field_name("type")
                    if type_node:
                        info["receiver_type"] = type_node.text.decode("utf-8")

        elif node.type in {"type_declaration", "type_spec"}:
            # Extract type name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["type_name"] = name_node.text.decode("utf-8")

            # Extract type kind
            for child in node.children:
                if child.type == "struct_type":
                    info["type_kind"] = "struct"
                    break
                if child.type == "interface_type":
                    info["type_kind"] = "interface"
                    break

        elif node.type == "package_clause":
            # Extract package name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["package_name"] = name_node.text.decode("utf-8")

        return info

    def get_context_nodes(self, node: Node) -> list[Node]:
        """Get nodes that provide context for a chunk."""
        context_nodes = []

        # Walk up to find package declaration
        current = node.parent
        while current:
            if current.type == "source_file":
                # Find package clause
                for child in current.children:
                    if child.type == "package_clause":
                        context_nodes.append(child)
                        break
                break
            current = current.parent

        # For methods, include the receiver type
        if node.type == "method_declaration":
            receiver = self._get_method_receiver(node)
            if receiver:
                context_nodes.append(receiver)

        return context_nodes

    def _has_name(self, node: Node) -> bool:
        """Check if a function has a name."""
        name_node = node.child_by_field_name("name")
        return name_node is not None and name_node.text != b""

    def _get_method_receiver(self, node: Node) -> Node | None:
        """Get the receiver type for a method."""
        params_node = node.child_by_field_name("parameters")
        if params_node and params_node.child_count > 0:
            first_param = params_node.children[0]
            if first_param.type == "parameter_declaration":
                return first_param.child_by_field_name("type")
        return None

    def merge_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks."""
        # Group methods by receiver type
        merged = []
        method_groups = {}

        for chunk in chunks:
            if chunk.node_type == "method_declaration":
                # Extract receiver type from chunk metadata
                receiver = chunk.metadata.get("receiver_type", "")
                if receiver:
                    if receiver not in method_groups:
                        method_groups[receiver] = []
                    method_groups[receiver].append(chunk)
                else:
                    merged.append(chunk)
            else:
                merged.append(chunk)

        # Add method groups (optionally merge them)
        for _receiver, methods in method_groups.items():
            # For now, just add them individually
            # Could merge into a single chunk representing the type's methods
            merged.extend(methods)

        return merged
