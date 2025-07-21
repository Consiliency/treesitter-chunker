"""Java language plugin."""

from typing import Set, List
from tree_sitter import Node
from .plugin_base import LanguagePlugin
from .base import LanguageConfig, ChunkRule, language_config_registry


class JavaPlugin(LanguagePlugin):
    """Plugin for Java language support."""

    @property
    def language_name(self) -> str:
        return "java"

    @property 
    def file_extensions(self) -> List[str]:
        return [".java"]

    def get_chunk_node_types(self) -> Set[str]:
        return {
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "annotation_type_declaration",
            "record_declaration",
            "method_declaration",
            "constructor_declaration",
            "field_declaration",
            "static_initializer",
        }

    def get_scope_node_types(self) -> Set[str]:
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
            "try_statement",
            "switch_expression",
            "lambda_expression",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False
            
        # Skip empty static/instance initializer blocks
        if node.type == "static_initializer":
            body = node.child_by_field_name("body")
            if body and body.child_count <= 2:  # Just braces
                return False
                
        # Skip synthetic/empty constructors
        if node.type == "constructor_declaration":
            body = node.child_by_field_name("body")
            if body and body.child_count <= 2:  # Just braces
                return False
                
        return True

    def extract_display_name(self, node: Node, source: bytes) -> str:
        """Extract display name for chunk."""
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode('utf-8')
                # Check for extends
                superclass = node.child_by_field_name("superclass")
                if superclass:
                    return f"{name} extends {superclass.text.decode('utf-8')}"
                return name
                
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                return f"interface {name_node.text.decode('utf-8')}"
                
        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                return f"enum {name_node.text.decode('utf-8')}"
                
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                method_name = name_node.text.decode('utf-8')
                # Include return type
                type_node = node.child_by_field_name("type")
                if type_node:
                    return f"{type_node.text.decode('utf-8')} {method_name}(...)"
                return f"{method_name}(...)"
                
        elif node.type == "constructor_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                return f"{name_node.text.decode('utf-8')}(...)"
                
        elif node.type == "field_declaration":
            # Extract type and field names
            type_node = node.child_by_field_name("type")
            type_str = type_node.text.decode('utf-8') if type_node else "?"
            
            # Find variable declarators
            field_names = []
            for child in node.children:
                if child.type == "variable_declarator":
                    name = child.child_by_field_name("name")
                    if name:
                        field_names.append(name.text.decode('utf-8'))
                        
            if field_names:
                return f"{type_str} {', '.join(field_names)}"
                
        return node.text.decode('utf-8')[:50]


# Register Java configuration
java_config = LanguageConfig(
    name="java",
    file_extensions=[".java"],
    chunk_rules=[
        ChunkRule(
            name="classes",
            node_types=[
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "annotation_type_declaration",
                "record_declaration"
            ],
            min_lines=1,
            max_lines=2000,
            include_context=True,
        ),
        ChunkRule(
            name="methods",
            node_types=["method_declaration", "constructor_declaration"],
            min_lines=1,
            max_lines=500,
            include_context=True,
        ),
        ChunkRule(
            name="fields",
            node_types=["field_declaration"],
            min_lines=1,
            max_lines=50,
            include_context=True,
        ),
        ChunkRule(
            name="static_blocks",
            node_types=["static_initializer"],
            min_lines=2,  # Skip empty blocks
            max_lines=200,
            include_context=True,
        ),
    ],
    scope_node_types=[
        "program",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "method_declaration",
        "constructor_declaration",
        "block",
    ],
)

# Register the configuration
language_config_registry.register(java_config)