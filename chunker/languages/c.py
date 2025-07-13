from __future__ import annotations
from typing import Set, Optional
from tree_sitter import Node

from .plugin_base import LanguagePlugin
from ..types import CodeChunk


class CPlugin(LanguagePlugin):
    """Plugin for C language chunking."""
    
    @property
    def language_name(self) -> str:
        return "c"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".c", ".h"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        return {
            "function_definition",
            "struct_specifier",
            "union_specifier",
            "enum_specifier",
            "type_definition",
        }
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract name from C nodes."""
        # For function definitions, look for the declarator
        if node.type == "function_definition":
            for child in node.children:
                if child.type == "function_declarator":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[subchild.start_byte:subchild.end_byte].decode('utf-8')
        
        # For structs, unions, enums - direct identifier child
        for child in node.children:
            if child.type == "identifier" or child.type == "type_identifier":
                return source[child.start_byte:child.end_byte].decode('utf-8')
                
        return None
    
    def get_context_for_children(self, node: Node, chunk: CodeChunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode())
        
        if name:
            if node.type == "struct_specifier":
                return f"struct {name}"
            elif node.type == "union_specifier":
                return f"union {name}"
            elif node.type == "enum_specifier":
                return f"enum {name}"
            elif node.type == "function_definition":
                return f"function {name}"
                
        return node.type