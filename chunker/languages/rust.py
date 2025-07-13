from __future__ import annotations
from typing import Set, Optional
from tree_sitter import Node

from .base import LanguagePlugin


class RustPlugin(LanguagePlugin):
    """Plugin for Rust language chunking."""
    
    @property
    def language_name(self) -> str:
        return "rust"
    
    @property
    def supported_extensions(self) -> Set[str]:
        return {".rs"}
    
    @property
    def default_chunk_types(self) -> Set[str]:
        return {
            "function_item",
            "impl_item",
            "trait_item",
            "struct_item",
            "enum_item",
            "mod_item",
            "macro_definition",
            "const_item",
            "static_item",
            "type_item"
        }
    
    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        """Extract the name from a Rust node."""
        # Look for identifier or type_identifier
        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                return source[child.start_byte:child.end_byte].decode('utf-8')
        return None
    
    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        # Get the name of the current node
        name = self.get_node_name(node, chunk.content.encode('utf-8'))
        
        if not name:
            return chunk.parent_context
            
        # For impl blocks, include the type being implemented
        if node.type == "impl_item":
            # Look for the type being implemented
            impl_type = None
            for child in node.children:
                if child.type in {"type_identifier", "generic_type", "reference_type", "pointer_type"}:
                    impl_type = source[child.start_byte:child.end_byte].decode('utf-8')
                    break
                    
            if impl_type:
                name = f"impl {impl_type}"
        
        # Build hierarchical context
        if chunk.parent_context:
            return f"{chunk.parent_context}::{name}"
        return name
    
    def process_node(
        self, 
        node: Node, 
        source: bytes, 
        file_path: str,
        parent_context: Optional[str] = None
    ):
        """Process Rust nodes with special handling."""
        # Skip test functions if configured
        if node.type == "function_item" and not self.config.custom_options.get("include_tests", True):
            # Check for #[test] attribute
            prev_sibling = node.prev_named_sibling
            if prev_sibling and prev_sibling.type == "attribute_item":
                attr_content = source[prev_sibling.start_byte:prev_sibling.end_byte].decode('utf-8')
                if "#[test]" in attr_content or "#[cfg(test)]" in attr_content:
                    return None
        
        # Check for visibility modifiers
        visibility = ""
        for child in node.children:
            if child.type == "visibility_modifier":
                visibility = source[child.start_byte:child.end_byte].decode('utf-8') + " "
                break
        
        # Create chunk with visibility info
        chunk = self.create_chunk(node, source, file_path, parent_context)
        if chunk and self.should_include_chunk(chunk):
            # Add visibility to node type for better context
            if visibility and visibility.strip() in {"pub", "pub(crate)", "pub(super)"}:
                chunk.node_type = f"{visibility.strip()}_{chunk.node_type}"
            return chunk
        
        return None