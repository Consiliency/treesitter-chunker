"""
Example of creating a custom language plugin for treesitter-chunker.

This example demonstrates:
1. Creating a custom plugin for a hypothetical language
2. Overriding default behavior
3. Adding custom configuration options
4. Plugin versioning and metadata
"""

import sys
from pathlib import Path

from tree_sitter import Node

sys.path.insert(0, str(Path(__file__).parent.parent))
from chunker import CodeChunk, get_plugin_manager
from chunker.languages.base import LanguagePlugin, PluginConfig


class GoPlugin(LanguagePlugin):
    """
    Example custom plugin for Go language.

    This demonstrates how to create a plugin for a language
    not included in the default set.
    """

    @staticmethod
    @property
    def language_name() -> str:
        return "go"

    @staticmethod
    @property
    def supported_extensions() -> set[str]:
        return {".go"}

    @staticmethod
    @property
    def default_chunk_types() -> set[str]:
        return {
            "function_declaration",
            "method_declaration",
            "type_declaration",
            "interface_declaration",
            "struct_declaration",
            "const_declaration",
            "var_declaration",
        }

    @staticmethod
    @property
    def plugin_version() -> str:
        return "1.1.0"

    @staticmethod
    @property
    def plugin_metadata() -> dict:
        """Add custom metadata."""
        metadata = super().plugin_metadata
        metadata.update(
            {
                "author": "Example Author",
                "description": "Go language support for treesitter-chunker",
                "go_version": "1.18+",
                "features": ["interfaces", "goroutines", "channels"],
            },
        )
        return metadata

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract name from Go nodes."""
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """Custom processing for Go nodes."""
        if node.type == "function_declaration" and not self.config.custom_options.get(
            "include_tests",
            True,
        ):
            name = self.get_node_name(node, source)
            if name and name.startswith(("Test", "Benchmark")):
                return None
        if node.type == "var_declaration":
            has_func_literal = False
            for child in node.walk():
                if child.type == "func_literal":
                    has_func_literal = True
                    break
            if not has_func_literal:
                return None
        if node.type == "method_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                for child in node.children:
                    if child.type == "parameter_list":
                        receiver_info = source[
                            child.start_byte : child.end_byte
                        ].decode("utf-8")
                        chunk.node_type = f"method{receiver_info}"
                        break
                return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk: CodeChunk) -> str:
        """Build Go-style context."""
        name = self.get_node_name(node, chunk.content.encode())
        if not name:
            return chunk.parent_context
        if node.type in {"interface_declaration", "struct_declaration"}:
            context_prefix = node.type.replace("_declaration", "")
            name = f"{context_prefix} {name}"
        if chunk.parent_context:
            return f"{chunk.parent_context}.{name}"
        return name


class MarkdownPlugin(LanguagePlugin):
    """
    Example plugin for non-programming languages.

    This demonstrates chunking markdown documents by headers.
    """

    @staticmethod
    @property
    def language_name() -> str:
        return "markdown"

    @staticmethod
    @property
    def supported_extensions() -> set[str]:
        return {".md", ".markdown", ".mdown"}

    @staticmethod
    @property
    def default_chunk_types() -> set[str]:
        return {"atx_heading", "setext_heading", "fenced_code_block"}

    @staticmethod
    @property
    def plugin_version() -> str:
        return "0.9.0"

    @staticmethod
    @property
    def minimum_api_version() -> str:
        return "1.0"

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract heading text from markdown nodes."""
        if node.type in {"atx_heading", "setext_heading"}:
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            return content.lstrip("#").strip()
        if node.type == "fenced_code_block":
            for child in node.children:
                if child.type == "info_string":
                    return f"code:{source[child.start_byte:child.end_byte].decode('utf-8')}"
            return "code:unknown"
        return None

    @staticmethod
    def process_node(
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """Custom processing for markdown nodes."""
        chunk = super().process_node(node, source, file_path, parent_context)
        if chunk and node.type in {"atx_heading", "setext_heading"}:
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if node.type == "atx_heading":
                level = len(content) - len(content.lstrip("#"))
                chunk.node_type = f"heading_level_{level}"
            else:
                chunk.node_type = "heading_level_1"
        return chunk

    def should_include_chunk(self, chunk: CodeChunk) -> bool:
        """Custom filtering for markdown chunks."""
        if chunk.node_type.startswith("heading"):
            return True
        if chunk.node_type.startswith("code:"):
            min_code_lines = self.config.custom_options.get("min_code_block_lines", 3)
            lines = chunk.end_line - chunk.start_line + 1
            return lines >= min_code_lines
        return super().should_include_chunk(chunk)


def demonstrate_custom_plugins():
    """Demonstrate using custom plugins."""
    print("=== Custom Plugin Demonstration ===\n")
    manager = get_plugin_manager()
    print("1. Registering custom plugins...")
    manager.registry.register(GoPlugin)
    manager.registry.register(MarkdownPlugin)
    go_plugin = manager.get_plugin("go")
    print("\nGo Plugin Metadata:")
    for key, value in go_plugin.plugin_metadata.items():
        print(f"  {key}: {value}")
    PluginConfig(
        chunk_types={
            "function_declaration",
            "method_declaration",
            "interface_declaration",
        },
        min_chunk_size=2,
        custom_options={"include_tests": False},
    )
    print("\n2. Processing Go code (hypothetical)...")
    print("  (Would process Go code if grammar was available)")
    PluginConfig(
        custom_options={"min_code_block_lines": 5, "include_yaml_frontmatter": True},
    )
    print("\n3. Processing Markdown (hypothetical)...")
    print("  (Would process Markdown if grammar was available)")
    print("\n4. All registered languages:")
    all_languages = manager.registry.list_languages()
    for lang in sorted(all_languages):
        plugin = manager.get_plugin(lang)
        print(f"  - {lang} (v{plugin.plugin_version})")
    print("\n5. File extension mappings:")
    extensions = manager.registry.list_extensions()
    for ext, lang in sorted(extensions.items()):
        print(f"  {ext} -> {lang}")


def demonstrate_plugin_loading():
    """Demonstrate loading plugins from a directory."""
    print("\n=== Plugin Directory Loading ===\n")
    custom_dir = Path("custom_plugins")
    custom_dir.mkdir(exist_ok=True)
    plugin_file = custom_dir / "go_plugin.py"
    plugin_file.write_text(
        """
from chunker.languages.base import LanguagePlugin
from typing import Set, Optional
from tree_sitter import Node

class GoPlugin(LanguagePlugin):
    @property
    def language_name(self) -> str:
        return "go"

    @property
    def supported_extensions(self) -> Set[str]:
        return {".go"}

    @property
    def default_chunk_types(self) -> Set[str]:
        return {"function_declaration", "method_declaration"}

    def get_node_name(self, node: Node, source: bytes) -> Optional[str]:
        for child in node.children:
            if child.type == "identifier":
                return source[child.start_byte:child.end_byte].decode('utf-8')
        return None
""",
    )
    manager = get_plugin_manager()
    loaded = manager.load_plugins_from_directory(custom_dir)
    print(f"Loaded {loaded} plugin(s) from {custom_dir}")
    plugin_file.unlink()
    custom_dir.rmdir()


if __name__ == "__main__":
    demonstrate_custom_plugins()
    demonstrate_plugin_loading()
