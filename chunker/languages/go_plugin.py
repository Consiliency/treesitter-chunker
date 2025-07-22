"""Language plugin."""

from typing import Set, List
from tree_sitter import Node
from .plugin_base import LanguagePlugin
from .base import LanguageConfig, ChunkRule, language_config_registry


class GoPlugin(LanguagePlugin):
    """Plugin for Go language support."""

    @property
    def language_name(self) -> str:
        return "go"

    @property
    def file_extensions(self) -> List[str]:
        return [".go"]

    def get_chunk_node_types(self) -> Set[str]:
        return {
            "function_declaration",
            "method_declaration", 
            "type_declaration",
            "type_spec",
            "const_declaration",
            "var_declaration",
        }

    def get_scope_node_types(self) -> Set[str]:
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
        """Determine if node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False
            
        # Skip anonymous functions
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if not name_node or not name_node.text:
                return False
        
        # For type specs, only chunk complex types
        if node.type == "type_spec":
            for child in node.children:
                if child.type in ["struct_type", "interface_type"]:
                    return True
            return False
            
        return True

    def extract_display_name(self, node: Node, source: bytes) -> str:
        """Extract display name for chunk."""
        if node.type in ["function_declaration", "method_declaration"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode('utf-8')
                
                # For methods, include receiver type
                if node.type == "method_declaration":
                    params = node.child_by_field_name("parameters")
                    if params and params.child_count > 0:
                        receiver = params.children[0]
                        if receiver.type == "parameter_declaration":
                            type_node = receiver.child_by_field_name("type")
                            if type_node:
                                receiver_type = type_node.text.decode('utf-8')
                                return f"({receiver_type}) {name}"
                
                return name
                
        elif node.type in ["type_declaration", "type_spec"]:
            name_node = node.child_by_field_name("name") 
            if name_node:
                return name_node.text.decode('utf-8')
                
        return node.text.decode('utf-8')[:50]


class GoConfig(LanguageConfig):
    """Language configuration for Go."""
    
    @property
    def language_id(self) -> str:
# Create Go configuration class
class GoConfig(LanguageConfig):
    """Go language configuration."""
    
    def __init__(self):
        super().__init__()
        self._chunk_rules = [
            ChunkRule(
                node_types={"function_declaration", "method_declaration"},
                include_children=True,
                priority=1,
                metadata={"name": "functions", "min_lines": 1, "max_lines": 500}
            ),
            ChunkRule(
                node_types={"type_declaration", "type_spec"},
                include_children=True,
                priority=1,
                metadata={"name": "types", "min_lines": 1, "max_lines": 300}
            ),
            ChunkRule(
                node_types={"const_declaration"},
                include_children=True,
                priority=1,
                metadata={"name": "constants", "min_lines": 1, "max_lines": 100}
            ),
            ChunkRule(
                node_types={"var_declaration"},
                include_children=True,
                priority=1,
                metadata={"name": "variables", "min_lines": 1, "max_lines": 50}
            ),
        ]
        
        self._scope_node_types = {
            "source_file",
            "function_declaration",
            "method_declaration",
            "block",
        }
        
        self._file_extensions = {".go"}
        
    @property
    def language_id(self) -> str:
        """Return the Go language identifier."""
        return "go"
    
    @property
    def chunk_types(self) -> Set[str]:
        """Go-specific chunk types."""
        return {
            "function_declaration",
            "method_declaration",
            "type_declaration",
            "type_spec",
            "interface_type",
            "const_declaration",
            "var_declaration",
        }
    
    @property
    def file_extensions(self) -> Set[str]:
        return {".go"}
    
    @property
    def ignore_types(self) -> Set[str]:
        """Types to ignore during traversal."""
        return {
            "comment",
            "line_comment",
            "block_comment",
        }
    
    def __init__(self):
        super().__init__()
        # Add Go-specific chunk rules
        self._chunk_rules = [
            ChunkRule(
                node_types={"function_declaration", "method_declaration"},
                metadata={"name": "functions", "min_lines": 1, "max_lines": 500, "include_context": True},
            ),
            ChunkRule(
                node_types={"type_declaration", "type_spec"},
                metadata={"name": "types", "min_lines": 1, "max_lines": 300, "include_context": True},
            ),
            ChunkRule(
                node_types={"const_declaration"},
                metadata={"name": "constants", "min_lines": 1, "max_lines": 100, "include_context": False},
            ),
            ChunkRule(
                node_types={"var_declaration"},
                metadata={"name": "variables", "min_lines": 1, "max_lines": 50, "include_context": False},
            ),
        ]


# Register Go configuration
go_config = GoConfig()
language_config_registry.register(go_config, aliases=["golang"])
        """Return the set of node types that should be treated as chunks."""
        chunk_types = set()
        for rule in self._chunk_rules:
            chunk_types.update(rule.node_types)
        return chunk_types
    
    @property
    def file_extensions(self) -> Set[str]:
        """Return Go file extensions."""
        return self._file_extensions

# Register the configuration
go_config = GoConfig()
language_config_registry.register(go_config)
