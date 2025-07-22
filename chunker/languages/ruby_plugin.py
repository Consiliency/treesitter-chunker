"""Ruby language plugin."""

from typing import Set, List
from tree_sitter import Node
from .plugin_base import LanguagePlugin
from .base import LanguageConfig, ChunkRule, language_config_registry


class RubyPlugin(LanguagePlugin):
    """Plugin for Ruby language support."""

    @property
    def language_name(self) -> str:
        return "ruby"

    @property
    def file_extensions(self) -> List[str]:
        return [".rb", ".rake", ".gemspec", ".ru"]

    def get_chunk_node_types(self) -> Set[str]:
        return {
            "method",
            "singleton_method",
            "class",
            "module", 
            "singleton_class",
            "block",  # For DSL blocks
            "lambda",
        }

    def get_scope_node_types(self) -> Set[str]:
        return {
            "program",
            "class",
            "module",
            "method",
            "singleton_method",
            "block",
            "lambda",
            "if",
            "unless",
            "case",
            "while",
            "until",
            "for",
            "begin",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False
            
        # Special handling for blocks - only chunk DSL blocks
        if node.type == "block":
            parent = node.parent
            if parent and parent.type == "call":
                method_node = parent.child_by_field_name("method")
                if method_node:
                    method_name = method_node.text.decode('utf-8')
                    # Common DSL methods
                    if method_name in ["describe", "context", "it", "before", "after",
                                     "namespace", "resources", "scope", "task", 
                                     "configure", "setup", "teardown"]:
                        return True
            return False
            
        # Skip anonymous lambdas
        if node.type == "lambda":
            # Ruby lambdas are typically anonymous
            return False
            
        return True

    def extract_display_name(self, node: Node, source: bytes) -> str:
        """Extract display name for chunk."""
        if node.type in ["method", "singleton_method"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                return name_node.text.decode('utf-8')
                
        elif node.type == "class":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode('utf-8')
                # Check for superclass
                superclass = node.child_by_field_name("superclass")
                if superclass:
                    return f"{name} < {superclass.text.decode('utf-8')}"
                return name
                
        elif node.type == "module":
            name_node = node.child_by_field_name("name")
            if name_node:
                return name_node.text.decode('utf-8')
                
        elif node.type == "block":
            # For DSL blocks, include the method call
            parent = node.parent
            if parent and parent.type == "call":
                method_node = parent.child_by_field_name("method")
                if method_node:
                    method_name = method_node.text.decode('utf-8')
                    # Try to get first argument (often a description)
                    args_node = parent.child_by_field_name("arguments")
                    if args_node and args_node.child_count > 0:
                        first_arg = args_node.children[0]
                        if first_arg.type in ["string", "symbol"]:
                            arg_text = first_arg.text.decode('utf-8').strip('"\'')
                            return f"{method_name} {arg_text}"
                    return method_name
                    
        return node.text.decode('utf-8')[:50]


<<<<<<< HEAD
# Create Ruby configuration class
class RubyConfig(LanguageConfig):
    """Ruby language configuration."""
    
    def __init__(self):
        super().__init__()
        self._chunk_rules = [
            ChunkRule(
                node_types={"method", "singleton_method"},
                include_children=True,
                priority=1,
                metadata={"name": "methods", "min_lines": 1, "max_lines": 300}
            ),
            ChunkRule(
                node_types={"class", "singleton_class"},
                include_children=True,
                priority=1,
                metadata={"name": "classes", "min_lines": 1, "max_lines": 1000}
            ),
            ChunkRule(
                node_types={"module"},
                include_children=True,
                priority=1,
                metadata={"name": "modules", "min_lines": 1, "max_lines": 1000}
            ),
            ChunkRule(
                node_types={"block"},
                include_children=True,
                priority=1,
                metadata={"name": "dsl_blocks", "min_lines": 1, "max_lines": 500}
            ),
        ]
        
        self._scope_node_types = {
            "program",
            "class",
            "module",
            "method",
            "singleton_method",
            "block",
        }
        
        self._file_extensions = {".rb", ".rake", ".gemspec", ".ru"}
        
    @property
    def language_id(self) -> str:
        """Return the Ruby language identifier."""
        return "ruby"
    
    @property
    def chunk_types(self) -> Set[str]:
        """Return the set of node types that should be treated as chunks."""
        chunk_types = set()
        for rule in self._chunk_rules:
            chunk_types.update(rule.node_types)
        return chunk_types
    
    @property
    def file_extensions(self) -> Set[str]:
        """Return Ruby file extensions."""
        return self._file_extensions

# Register the configuration
ruby_config = RubyConfig()
language_config_registry.register(ruby_config)
=======
# Register Ruby configuration
# TODO: Fix this to use the proper ChunkRule interface
# ruby_config = LanguageConfig(
#     name="ruby",
#     file_extensions=[".rb", ".rake", ".gemspec", ".ru"],
#     chunk_rules=[
#         ChunkRule(
#             name="methods",
#             node_types=["method", "singleton_method"],
#             min_lines=1,
#             max_lines=300,
#             include_context=True,
#         ),
#         ChunkRule(
#             name="classes",
#             node_types=["class", "singleton_class"],
#             min_lines=1,
#             max_lines=1000,
#             include_context=True,
#         ),
#         ChunkRule(
#             name="modules",
#             node_types=["module"],
#             min_lines=1,
#             max_lines=1000,
#             include_context=True,
#         ),
#         ChunkRule(
#             name="dsl_blocks",
#             node_types=["block"],
#             min_lines=1,
#             max_lines=500,
#             include_context=True,
#             # Custom filter will be applied in should_chunk_node
#         ),
#     ],
#     scope_node_types=[
#         "program",
#         "class",
#         "module",
#         "method",
#         "singleton_method",
#         "block",
#     ],
# )
# 
# # Register the configuration
# language_config_registry.register(ruby_config)
>>>>>>> 437636e (Implement Phase 9 chunk hierarchy building)
