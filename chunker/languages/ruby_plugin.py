"""Ruby language plugin."""

from tree_sitter import Node

from .base import ChunkRule, LanguageConfig, language_config_registry
from .plugin_base import LanguagePlugin


class RubyPlugin(LanguagePlugin):
    """Plugin for Ruby language support."""

    @property
    def language_name(self) -> str:
        return "ruby"

    @property
    def file_extensions(self) -> list[str]:
        return [".rb", ".rake", ".gemspec", "Rakefile", "Gemfile"]

    def get_chunk_node_types(self) -> set[str]:
        return {
            "method",
            "singleton_method",
            "class",
            "module",
            "do_block",
            "lambda",
        }

    def get_scope_node_types(self) -> set[str]:
        return {
            "program",
            "class",
            "module",
            "method",
            "singleton_method",
            "do_block",
            "block",
            "if",
            "unless",
            "case",
            "while",
            "for",
            "begin",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False

        # For blocks, only chunk larger ones
        if node.type in ["do_block", "block"]:
            # Count non-trivial lines
            line_count = node.end_point[0] - node.start_point[0] + 1
            if line_count < 5:  # Skip small blocks
                return False

        # Skip inline lambdas
        if node.type == "lambda":
            if node.end_point[0] == node.start_point[0]:  # Single line
                return False

        return True

    def extract_display_name(self, node: Node, _source: bytes) -> str:
        """Extract display name for chunk."""
        if node.type == "class":
            # Find constant node for class name
            for child in node.children:
                if child.type == "constant":
                    return f"class {child.text.decode('utf-8')}"
                if child.type == "scope_resolution":
                    # Handle nested classes like Module::Class
                    return f"class {child.text.decode('utf-8')}"

        elif node.type == "module":
            # Find constant node for module name
            for child in node.children:
                if child.type in {"constant", "scope_resolution"}:
                    return f"module {child.text.decode('utf-8')}"

        elif node.type in ["method", "singleton_method"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                method_name = name_node.text.decode("utf-8")
                if node.type == "singleton_method":
                    object_node = node.child_by_field_name("object")
                    if object_node:
                        return f"def {object_node.text.decode('utf-8')}.{method_name}"
                    return f"def self.{method_name}"
                return f"def {method_name}"

        elif node.type == "do_block":
            # Try to get context from the method call
            parent = node.parent
            if parent and parent.type == "method_call":
                method_node = parent.child_by_field_name("method")
                if method_node:
                    return f"{method_node.text.decode('utf-8')} do...end"
            return "do...end block"

        elif node.type == "lambda":
            # Check if it's a stabby lambda
            if node.text.startswith(b"->"):
                # Extract parameters if any
                params_node = node.child_by_field_name("parameters")
                if params_node:
                    return f"-> {params_node.text.decode('utf-8')} {{ ... }}"
                return "-> { ... }"
            # Traditional lambda
            args_node = node.child_by_field_name("arguments")
            if args_node and args_node.child_count > 0:
                # Try to get first argument for context
                first_arg = args_node.children[0]
                if first_arg.type in ["string", "symbol"]:
                    arg_text = first_arg.text.decode("utf-8").strip("\"'")
                    return f"{method_name} {arg_text}"
            return method_name

        return node.text.decode("utf-8")[:50]


class RubyConfig(LanguageConfig):
    """Ruby language configuration."""

    def __init__(self):
        super().__init__()
        self._chunk_rules = [
            ChunkRule(
                node_types={"method", "singleton_method"},
                include_children=True,
                priority=1,
                metadata={"name": "methods", "min_lines": 1, "max_lines": 500},
            ),
            ChunkRule(
                node_types={"class", "module"},
                include_children=True,
                priority=1,
                metadata={"name": "classes_modules", "min_lines": 1, "max_lines": 2000},
            ),
            ChunkRule(
                node_types={"do_block", "lambda"},
                include_children=True,
                priority=2,
                metadata={"name": "blocks", "min_lines": 5, "max_lines": 100},
            ),
        ]

        self._scope_node_types = {
            "program",
            "class",
            "module",
            "method",
            "singleton_method",
            "do_block",
            "block",
        }

        self._file_extensions = {".rb", ".rake", ".gemspec"}

    @property
    def language_id(self) -> str:
        """Return the Ruby language identifier."""
        return "ruby"

    @property
    def chunk_types(self) -> set[str]:
        """Return the set of node types that should be treated as chunks."""
        chunk_types = set()
        for rule in self._chunk_rules:
            chunk_types.update(rule.node_types)
        return chunk_types

    @property
    def file_extensions(self) -> set[str]:
        """Return Ruby file extensions."""
        return self._file_extensions


# Register the configuration
ruby_config = RubyConfig()
language_config_registry.register(ruby_config)
