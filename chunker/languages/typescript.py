"""TypeScript language configuration and plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.utils.text import safe_decode_bytes

from .base import LanguageConfig, language_config_registry
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node

    from chunker.types import CodeChunk


class TypeScriptConfig(LanguageConfig):
    """Language configuration for TypeScript."""

    @property
    def language_id(self) -> str:
        return "typescript"

    @property
    def chunk_types(self) -> set[str]:
        """TypeScript-specific chunk types including TS-specific constructs."""
        return {
            # JavaScript-like constructs
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "import_statement",
            "variable_declarator",
            # TypeScript-specific constructs
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
            "abstract_class_declaration",
            "internal_module",  # namespace
            "module",  # module declaration
            "function_signature",
            "method_signature",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".ts", ".d.ts"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("comment")
        self.add_ignore_type("template_string")


class TSXConfig(LanguageConfig):
    """Language configuration for TSX (TypeScript with JSX)."""

    @property
    def language_id(self) -> str:
        return "tsx"

    @property
    def name(self) -> str:
        return "tsx"

    @property
    def chunk_types(self) -> set[str]:
        """TSX chunk types - includes TypeScript plus JSX elements."""
        return {
            # JavaScript/TypeScript constructs
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "import_statement",
            "variable_declarator",
            # TypeScript-specific constructs
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
            "abstract_class_declaration",
            "internal_module",  # namespace
            "module",  # module declaration
            "function_signature",
            "method_signature",
            # JSX constructs
            "jsx_element",
            "jsx_fragment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".tsx"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("comment")
        self.add_ignore_type("template_string")


class TypeScriptPlugin(LanguagePlugin):
    """Plugin for TypeScript language chunking."""

    @property
    def language_name(self) -> str:
        return "typescript"

    @property
    def supported_extensions(self) -> set[str]:
        return {".ts", ".tsx", ".d.ts"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
            "abstract_class_declaration",
            "internal_module",
            "module",
            "variable_declarator",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract name from TypeScript nodes."""
        # Handle TypeScript-specific nodes
        if (
            node.type == "interface_declaration"
            or node.type == "type_alias_declaration"
        ):
            for child in node.children:
                if child.type == "type_identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type == "enum_declaration":
            for child in node.children:
                if child.type == "identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        elif node.type in {"internal_module", "module"}:
            # Namespace or module declaration
            for child in node.children:
                if child.type in {"identifier", "string"}:
                    name = safe_decode_bytes(source[child.start_byte : child.end_byte])
                    # Remove quotes from string module names
                    return name.strip("\"'")
        elif node.type == "abstract_class_declaration":
            for child in node.children:
                if child.type == "type_identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])

        # Handle standard JavaScript/TypeScript nodes
        for child in node.children:
            if child.type == "identifier" or child.type == "type_identifier":
                return safe_decode_bytes(source[child.start_byte : child.end_byte])

        # Method definitions
        if node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])

        # Variable declarator with function
        if node.type == "variable_declarator":
            for child in node.children:
                if child.type == "identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])

        return None

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode())
        if name:
            if node.type == "class_declaration":
                return f"class {name}"
            if node.type == "abstract_class_declaration":
                return f"abstract class {name}"
            if node.type == "interface_declaration":
                return f"interface {name}"
            if node.type == "type_alias_declaration":
                return f"type {name}"
            if node.type == "enum_declaration":
                return f"enum {name}"
            if node.type in {"internal_module", "module"}:
                return f"namespace {name}"
            if node.type in {
                "function_declaration",
                "function_expression",
                "arrow_function",
            }:
                return f"function {name}"
            if node.type == "method_definition":
                return f"method {name}"

        # Fallback to node type
        if node.type == "internal_module":
            return "namespace"
        if node.type == "module":
            return "module"
        return node.type

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """Process TypeScript nodes with special handling."""
        # Handle variable declarators - only chunk if they contain function-like expressions
        if node.type == "variable_declarator":
            has_function = False
            for child in node.children:
                if child.type in {"arrow_function", "function_expression"}:
                    has_function = True
                    break
            if not has_function:
                return None

        # Handle export statements - delegate to the exported construct
        if node.type == "export_statement":
            for child in node.children:
                if child.type in self.chunk_node_types:
                    return self.process_node(child, source, file_path, parent_context)

        # Process the node normally
        return super().process_node(node, source, file_path, parent_context)

    def create_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk:
        """Create a CodeChunk from a node with TypeScript metadata."""
        chunk = super().create_chunk(node, source, file_path, parent_context)

        # Set proper metadata type for TypeScript-specific nodes
        if node.type == "interface_declaration":
            chunk.metadata["type"] = "interface_declaration"
        elif node.type == "type_alias_declaration":
            chunk.metadata["type"] = "type_alias_declaration"
        elif node.type == "enum_declaration":
            chunk.metadata["type"] = "enum_declaration"
        elif node.type in {"internal_module", "module"}:
            chunk.metadata["type"] = "namespace_declaration"
        elif node.type == "abstract_class_declaration":
            chunk.metadata["type"] = "class_declaration"
            chunk.metadata["abstract"] = True
        else:
            # For standard JS/TS nodes, use the node type
            chunk.metadata["type"] = node.type

        return chunk


# Register the TypeScript configurations
typescript_config = TypeScriptConfig()
tsx_config = TSXConfig()

language_config_registry.register(typescript_config)
language_config_registry.register(tsx_config)
