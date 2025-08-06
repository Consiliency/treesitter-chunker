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

    @staticmethod
    def get_chunk_node_types() -> set[str]:
        """Get node types that should be chunked."""
        return {
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "annotation_type_declaration",
            "record_declaration",
            "method_declaration",
            "constructor_declaration",
            "field_declaration",
            "class_body",
            "static_initializer",
            "block",
        }

    @staticmethod
    def get_scope_node_types() -> set[str]:
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
        if (
            node.type == "class_body"
            and node.parent
            and node.parent.type != "class_declaration"
        ):
            return False
        if (
            node.type
            in {
                "static_initializer",
                "block",
            }
            and node.child_count <= 2
        ):
            return False
        if node.type == "constructor_declaration":
            body = node.child_by_field_name("body")
            if body and body.child_count <= 2:
                return False
        return True

    def extract_chunk_info(self, node: Node, _source_code: bytes) -> dict:
        """Extract additional information for a chunk."""
        info = {}
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["class_name"] = name_node.text.decode("utf-8")
            info["modifiers"] = self._extract_modifiers(node)
            superclass = node.child_by_field_name("superclass")
            if superclass:
                info["extends"] = superclass.text.decode("utf-8")
            interfaces = node.child_by_field_name("interfaces")
            if interfaces:
                info["implements"] = self._extract_interface_list(interfaces)
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["interface_name"] = name_node.text.decode("utf-8")
            info["modifiers"] = self._extract_modifiers(node)
            extends = node.child_by_field_name("extends")
            if extends:
                info["extends"] = self._extract_interface_list(extends)
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["method_name"] = name_node.text.decode("utf-8")
            type_node = node.child_by_field_name("type")
            if type_node:
                info["return_type"] = type_node.text.decode("utf-8")
            info["modifiers"] = self._extract_modifiers(node)
            params = node.child_by_field_name("parameters")
            if params:
                info["parameters"] = self._extract_parameters(params)
            if (
                info.get("method_name") == "main"
                and "static" in info.get("modifiers", [])
                and "public" in info.get("modifiers", [])
            ):
                info["is_main"] = True
        elif node.type == "constructor_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["constructor_name"] = name_node.text.decode("utf-8")
            info["modifiers"] = self._extract_modifiers(node)
            params = node.child_by_field_name("parameters")
            if params:
                info["parameters"] = self._extract_parameters(params)
        elif node.type == "field_declaration":
            type_node = node.child_by_field_name("type")
            if type_node:
                info["field_type"] = type_node.text.decode("utf-8")
            declarator = node.child_by_field_name("declarator")
            if declarator:
                info["field_names"] = self._extract_field_names(declarator)
            info["modifiers"] = self._extract_modifiers(node)
        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["enum_name"] = name_node.text.decode("utf-8")
            info["modifiers"] = self._extract_modifiers(node)
        return info

    @staticmethod
    def get_context_nodes(node: Node) -> list[Node]:
        """Get nodes that provide context for a chunk."""
        context_nodes = []
        current = node.parent
        while current:
            if current.type in {
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
            }:
                context_nodes.append(current)
            elif current.type == "program":
                for child in current.children:
                    if child.type == "package_declaration":
                        context_nodes.append(child)
                        break
                break
            current = current.parent
        return context_nodes

    @staticmethod
    def _extract_modifiers(node: Node) -> list[str]:
        """Extract modifiers from a declaration."""
        modifiers = []
        for child in node.children:
            if child.type == "modifiers":
                for modifier in child.children:
                    if modifier.type in {
                        "public",
                        "private",
                        "protected",
                        "static",
                        "final",
                        "abstract",
                        "synchronized",
                        "volatile",
                    }:
                        modifiers.append(modifier.type)
                    elif modifier.type == "annotation":
                        name = modifier.child_by_field_name("name")
                        if name:
                            modifiers.append(f"@{name.text.decode('utf-8')}")
        return modifiers

    @staticmethod
    def _extract_interface_list(interfaces_node: Node) -> list[str]:
        """Extract list of interface names."""
        interfaces = [
            child.text.decode("utf-8")
            for child in interfaces_node.children
            if child.type in {"type_identifier", "scoped_type_identifier"}
        ]
        return interfaces

    @staticmethod
    def _extract_parameters(params_node: Node) -> list[dict]:
        """Extract parameter information."""
        parameters = []
        for child in params_node.children:
            if child.type == "formal_parameter":
                param = {}
                type_node = child.child_by_field_name("type")
                if type_node:
                    param["type"] = type_node.text.decode("utf-8")
                name_node = child.child_by_field_name("name")
                if name_node:
                    param["name"] = name_node.text.decode("utf-8")
                parameters.append(param)
        return parameters

    @staticmethod
    def _extract_field_names(declarator_node: Node) -> list[str]:
        """Extract field names from a variable declarator."""
        names = []
        if declarator_node.type == "variable_declarator":
            name_node = declarator_node.child_by_field_name("name")
            if name_node:
                names.append(name_node.text.decode("utf-8"))
        else:
            for child in declarator_node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        names.append(name_node.text.decode("utf-8"))
        return names

    @staticmethod
    def merge_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks."""
        merged = []
        field_groups = {}
        other_chunks = []
        for chunk in chunks:
            if chunk.node_type == "field_declaration":
                parent_class = chunk.parent_context
                if parent_class:
                    if parent_class not in field_groups:
                        field_groups[parent_class] = []
                    field_groups[parent_class].append(chunk)
                else:
                    other_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        for fields in field_groups.values():
            merged.extend(fields)
        merged.extend(other_chunks)
        merged.sort(key=lambda c: c.byte_start)
        return merged
