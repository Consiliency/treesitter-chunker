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


class JavaConfig(LanguageConfig):
    """Java language configuration."""
    
    def __init__(self):
        super().__init__()
        self._chunk_rules = [
            ChunkRule(
                node_types={
                    "class_declaration",
                    "interface_declaration",
                    "enum_declaration",
                    "annotation_type_declaration",
                    "record_declaration"
                },
                include_children=True,
                priority=1,
                metadata={"name": "classes", "min_lines": 1, "max_lines": 2000}
            ),
            ChunkRule(
                node_types={"method_declaration", "constructor_declaration"},
                include_children=True,
                priority=1,
                metadata={"name": "methods", "min_lines": 1, "max_lines": 500}
            ),
            ChunkRule(
                node_types={"field_declaration"},
                include_children=True,
                priority=1,
                metadata={"name": "fields", "min_lines": 1, "max_lines": 50}
            ),
            ChunkRule(
                node_types={"static_initializer"},
                include_children=True,
                priority=1,
                metadata={"name": "static_blocks", "min_lines": 2, "max_lines": 200}
            ),
        ]
        
        self._scope_node_types = {
            "program",
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
            "block",
        }
        
        self._file_extensions = {".java"}
        
    @property
    def language_id(self) -> str:
        """Return the Java language identifier."""
        return "java"
    
    @property
    def chunk_types(self) -> Set[str]:
        """Return the set of node types that should be treated as chunks."""
        chunk_types = set()
        for rule in self._chunk_rules:
            chunk_types.update(rule.node_types)
        return chunk_types
    
    @property
    def file_extensions(self) -> Set[str]:
        """Return Java file extensions."""
        return self._file_extensions

# Register the configuration
java_config = JavaConfig()
language_config_registry.register(java_config)