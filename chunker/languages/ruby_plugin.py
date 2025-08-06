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

    @staticmethod
    def get_chunk_node_types() -> set[str]:
        return {"method", "singleton_method", "class", "module", "do_block", "lambda"}

    @staticmethod
    def get_scope_node_types() -> set[str]:
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
        if node.type in {"do_block", "block"}:
            line_count = node.end_point[0] - node.start_point[0] + 1
            if line_count < 5:
                return False
        return not (node.type == "lambda" and node.end_point[0] == node.start_point[0])

    @staticmethod
    def extract_display_name(node: Node, _source: bytes) -> str:
        """Extract display name for chunk."""
        extractors = {
            "class": RubyPlugin._extract_class_name,
            "module": RubyPlugin._extract_module_name,
            "method": RubyPlugin._extract_method_name,
            "singleton_method": RubyPlugin._extract_singleton_method_name,
            "do_block": RubyPlugin._extract_do_block_name,
            "lambda": RubyPlugin._extract_lambda_name,
        }

        extractor = extractors.get(node.type)
        if extractor:
            return extractor(node)

        return node.text.decode("utf-8")[:50]

    @staticmethod
    def _extract_class_name(node: Node) -> str:
        """Extract class declaration name."""
        for child in node.children:
            if child.type in {"constant", "scope_resolution"}:
                return f"class {child.text.decode('utf-8')}"
        return "class"

    @staticmethod
    def _extract_module_name(node: Node) -> str:
        """Extract module declaration name."""
        for child in node.children:
            if child.type in {"constant", "scope_resolution"}:
                return f"module {child.text.decode('utf-8')}"
        return "module"

    @staticmethod
    def _extract_method_name(node: Node) -> str:
        """Extract method declaration name."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return f"def {name_node.text.decode('utf-8')}"
        return "def"

    @staticmethod
    def _extract_singleton_method_name(node: Node) -> str:
        """Extract singleton method name."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return "def self.method"

        method_name = name_node.text.decode("utf-8")
        object_node = node.child_by_field_name("object")
        if object_node:
            return f"def {object_node.text.decode('utf-8')}.{method_name}"
        return f"def self.{method_name}"

    @staticmethod
    def _extract_do_block_name(node: Node) -> str:
        """Extract do block name."""
        parent = node.parent
        if parent and parent.type == "method_call":
            method_node = parent.child_by_field_name("method")
            if method_node:
                return f"{method_node.text.decode('utf-8')} do...end"
        return "do...end block"

    @staticmethod
    def _extract_lambda_name(node: Node) -> str:
        """Extract lambda name."""
        if node.text.startswith(b"->"):
            params_node = node.child_by_field_name("parameters")
            if params_node:
                return f"-> {params_node.text.decode('utf-8')} {{ ... }}"
            return "-> { ... }"

        # Old-style lambda - this part seems broken in original code
        # Using a simple fallback
        return "lambda { ... }"


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
                node_types={
                    "do_block",
                    "lambda",
                },
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


ruby_config = RubyConfig()
language_config_registry.register(ruby_config)
