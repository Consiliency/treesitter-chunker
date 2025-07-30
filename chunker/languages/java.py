"""Java language support for chunking."""

from tree_sitter import Node

from chunker.types import CodeChunk

from .base import LanguageChunker


class JavaChunker(LanguageChunker):
    """Chunker implementation for Java."""

    @property
    def language_name(self) -> str:
        """Get the language name."""
        return "java"

    @property
    def file_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".java"]

    def get_chunk_node_types(self) -> set[str]:
        """Get node types that should be chunked."""
        return {
            # Classes and interfaces
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "annotation_type_declaration",
            "record_declaration",
            # Methods and constructors
            "method_declaration",
            "constructor_declaration",
            # Fields
            "field_declaration",
            # Inner types
            "class_body",  # For anonymous classes
            # Static blocks
            "static_initializer",
            "block",  # Instance initializer blocks
        }

    def get_scope_node_types(self) -> set[str]:
        """Get node types that define scopes."""
        return {
            "program",
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
            "block",
            "if_statement",
            "for_statement",
            "while_statement",
            "do_statement",
            "switch_expression",
            "try_statement",
            "lambda_expression",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False

        # Skip anonymous classes (handled separately)
        if (
            node.type == "class_body"
            and node.parent
            and node.parent.type != "class_declaration"
        ):
            return False

        # Skip empty static/instance initializer blocks
        if node.type in ["static_initializer", "block"]:
            if node.child_count <= 2:  # Just braces
                return False

        # Skip synthetic constructors
        if node.type == "constructor_declaration":
            # Check if it's a default constructor
            body = node.child_by_field_name("body")
            if body and body.child_count <= 2:  # Just braces
                return False

        return True

    def extract_chunk_info(self, node: Node, _source_code: bytes) -> dict:
        """Extract additional information for a chunk."""
        info = {}

        if node.type == "class_declaration":
            # Extract class name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["class_name"] = name_node.text.decode("utf-8")

            # Extract modifiers
            info["modifiers"] = self._extract_modifiers(node)

            # Extract superclass
            superclass = node.child_by_field_name("superclass")
            if superclass:
                info["extends"] = superclass.text.decode("utf-8")

            # Extract interfaces
            interfaces = node.child_by_field_name("interfaces")
            if interfaces:
                info["implements"] = self._extract_interface_list(interfaces)

        elif node.type == "interface_declaration":
            # Extract interface name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["interface_name"] = name_node.text.decode("utf-8")

            info["modifiers"] = self._extract_modifiers(node)

            # Extract extended interfaces
            extends = node.child_by_field_name("extends")
            if extends:
                info["extends"] = self._extract_interface_list(extends)

        elif node.type == "method_declaration":
            # Extract method name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["method_name"] = name_node.text.decode("utf-8")

            # Extract return type
            type_node = node.child_by_field_name("type")
            if type_node:
                info["return_type"] = type_node.text.decode("utf-8")

            # Extract modifiers
            info["modifiers"] = self._extract_modifiers(node)

            # Extract parameters
            params = node.child_by_field_name("parameters")
            if params:
                info["parameters"] = self._extract_parameters(params)

            # Check if it's a main method
            if (
                info.get("method_name") == "main"
                and "static" in info.get("modifiers", [])
                and "public" in info.get("modifiers", [])
            ):
                info["is_main"] = True

        elif node.type == "constructor_declaration":
            # Extract constructor name (same as class)
            name_node = node.child_by_field_name("name")
            if name_node:
                info["constructor_name"] = name_node.text.decode("utf-8")

            info["modifiers"] = self._extract_modifiers(node)

            # Extract parameters
            params = node.child_by_field_name("parameters")
            if params:
                info["parameters"] = self._extract_parameters(params)

        elif node.type == "field_declaration":
            # Extract field info
            type_node = node.child_by_field_name("type")
            if type_node:
                info["field_type"] = type_node.text.decode("utf-8")

            # Extract field names
            declarator = node.child_by_field_name("declarator")
            if declarator:
                info["field_names"] = self._extract_field_names(declarator)

            info["modifiers"] = self._extract_modifiers(node)

        elif node.type == "enum_declaration":
            # Extract enum name
            name_node = node.child_by_field_name("name")
            if name_node:
                info["enum_name"] = name_node.text.decode("utf-8")

            info["modifiers"] = self._extract_modifiers(node)

        return info

    def get_context_nodes(self, node: Node) -> list[Node]:
        """Get nodes that provide context for a chunk."""
        context_nodes = []

        # Walk up to find containing class/interface
        current = node.parent
        while current:
            if current.type in [
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
            ]:
                context_nodes.append(current)
            elif current.type == "program":
                # Find package declaration
                for child in current.children:
                    if child.type == "package_declaration":
                        context_nodes.append(child)
                        break
                break
            current = current.parent

        return context_nodes

    def _extract_modifiers(self, node: Node) -> list[str]:
        """Extract modifiers from a declaration."""
        modifiers = []

        # Look for modifiers node
        for child in node.children:
            if child.type == "modifiers":
                for modifier in child.children:
                    if modifier.type in [
                        "public",
                        "private",
                        "protected",
                        "static",
                        "final",
                        "abstract",
                        "synchronized",
                        "volatile",
                    ]:
                        modifiers.append(modifier.type)
                    elif modifier.type == "annotation":
                        # Include annotation names
                        name = modifier.child_by_field_name("name")
                        if name:
                            modifiers.append(f"@{name.text.decode('utf-8')}")

        return modifiers

    def _extract_interface_list(self, interfaces_node: Node) -> list[str]:
        """Extract list of interface names."""
        interfaces = []
        for child in interfaces_node.children:
            if child.type in {"type_identifier", "scoped_type_identifier"}:
                interfaces.append(child.text.decode("utf-8"))
        return interfaces

    def _extract_parameters(self, params_node: Node) -> list[dict]:
        """Extract parameter information."""
        parameters = []
        for child in params_node.children:
            if child.type == "formal_parameter":
                param = {}

                # Get type
                type_node = child.child_by_field_name("type")
                if type_node:
                    param["type"] = type_node.text.decode("utf-8")

                # Get name
                name_node = child.child_by_field_name("name")
                if name_node:
                    param["name"] = name_node.text.decode("utf-8")

                parameters.append(param)

        return parameters

    def _extract_field_names(self, declarator_node: Node) -> list[str]:
        """Extract field names from a variable declarator."""
        names = []

        if declarator_node.type == "variable_declarator":
            name_node = declarator_node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))
        else:
            # Multiple declarators
            for child in declarator_node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        names.append(name_node.text.decode("utf-8"))

        return names

    def merge_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks."""
        merged = []

        # Group field declarations in the same class
        field_groups = {}
        other_chunks = []

        for chunk in chunks:
            if chunk.node_type == "field_declaration":
                # Find parent class
                parent_class = chunk.parent_context
                if parent_class:
                    if parent_class not in field_groups:
                        field_groups[parent_class] = []
                    field_groups[parent_class].append(chunk)
                else:
                    other_chunks.append(chunk)
            else:
                other_chunks.append(chunk)

        # Optionally merge field groups
        # For now, keep them separate for clarity
        for fields in field_groups.values():
            merged.extend(fields)

        merged.extend(other_chunks)

        # Sort by appearance order
        merged.sort(key=lambda c: c.byte_start)

        return merged
