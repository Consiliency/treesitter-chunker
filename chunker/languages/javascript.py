from __future__ import annotations
from typing import Set, Optional
from tree_sitter import Node

from .base import LanguageConfig, ChunkRule
from .plugin_base import LanguagePlugin
from ..types import CodeChunk


class JavaScriptConfig(LanguageConfig):
    """Language configuration for JavaScript."""
    
    @property
    def language_id(self) -> str:
        return "javascript"
    
    @property
    def chunk_types(self) -> Set[str]:
        """JavaScript-specific chunk types."""
        return {
            # Functions
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            
            # Classes
            "class_declaration",
            "method_definition",
            
            # Modules
            "export_statement",
            "import_statement",
            
            # Variables with functions
            "variable_declarator",
        }
    
    @property
    def file_extensions(self) -> Set[str]:
        return {".js", ".jsx", ".mjs", ".cjs"}
    
    def __init__(self):
        super().__init__()
        
        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("template_string")


# Register the JavaScript configuration
from . import language_config_registry
language_config_registry.register(JavaScriptConfig(), aliases=["js", "jsx"])


class JavaScriptPlugin(LanguagePlugin):
    """Plugin for JavaScript/TypeScript language chunking."""
    
    @property
    def language_name(self) -> str:
        return "javascript"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        return {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
            "variable_declarator",  # For const/let/var with functions
        }
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract name from JavaScript nodes."""
        # Direct identifier child
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte:child.end_byte].decode('utf-8')
                
        # For method definitions, check property_identifier
        if node.type == "method_definition":
            for child in node.children:
                if child.type == "property_identifier":
                    return source[child.start_byte:child.end_byte].decode('utf-8')
                    
        # For variable declarators, check the name pattern
        if node.type == "variable_declarator":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode('utf-8')
                    
        return None
    
    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode())
        
        if name:
            if node.type == "class_declaration":
                return f"class {name}"
            elif node.type in ("function_declaration", "function_expression", "arrow_function"):
                return f"function {name}"
            elif node.type == "method_definition":
                return f"method {name}"
                
        return node.type
    
    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: Optional[str] = None
    ) -> Optional[CodeChunk]:
        """Process JavaScript nodes with special handling."""
        # Only include variable declarators that contain functions
        if node.type == "variable_declarator":
            has_function = False
            for child in node.children:
                if child.type in ("arrow_function", "function_expression"):
                    has_function = True
                    break
                    
            if not has_function:
                return None
                
        # Handle export statements
        if node.type == "export_statement":
            # Look for the actual declaration inside
            for child in node.children:
                if child.type in self.chunk_node_types:
                    return self.process_node(child, source, file_path, parent_context)
                    
        return super().process_node(node, source, file_path, parent_context)