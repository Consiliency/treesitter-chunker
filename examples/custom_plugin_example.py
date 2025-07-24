#!/usr/bin/env python3
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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker import CodeChunk, get_plugin_manager
from chunker.languages.base import LanguagePlugin, PluginConfig


class GoPlugin(LanguagePlugin):
    """
    Example custom plugin for Go language.

    This demonstrates how to create a plugin for a language
    not included in the default set.
    """

    @property
    def language_name(self) -> str:
        return "go"

    @property
    def supported_extensions(self) -> set[str]:
        return {".go"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "method_declaration",
            "type_declaration",
            "interface_declaration",
            "struct_declaration",
            "const_declaration",
            "var_declaration",  # For package-level variables
        }

    @property
    def plugin_version(self) -> str:
        return "1.1.0"

    @property
    def plugin_metadata(self) -> dict:
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

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract name from Go nodes."""
        # Look for identifier nodes
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
        # Skip test functions if configured
        if node.type == "function_declaration" and not self.config.custom_options.get(
            "include_tests",
            True,
        ):

            name = self.get_node_name(node, source)
            if name and (name.startswith("Test") or name.startswith("Benchmark")):
                return None

        # Handle package-level var declarations
        if node.type == "var_declaration":
            # Only include if it contains a function literal
            has_func_literal = False
            for child in node.walk():
                if child.type == "func_literal":
                    has_func_literal = True
                    break

            if not has_func_literal:
                return None

        # Add receiver information for methods
        if node.type == "method_declaration":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                # Extract receiver type
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

        # For interfaces and structs, include the type
        if node.type in {"interface_declaration", "struct_declaration"}:
            context_prefix = node.type.replace("_declaration", "")
            name = f"{context_prefix} {name}"

        # Build hierarchical context with dot notation
        if chunk.parent_context:
            return f"{chunk.parent_context}.{name}"
        return name


class MarkdownPlugin(LanguagePlugin):
    """
    Example plugin for non-programming languages.

    This demonstrates chunking markdown documents by headers.
    """

    @property
    def language_name(self) -> str:
        return "markdown"

    @property
    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown", ".mdown"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "atx_heading",  # # Headers
            "setext_heading",  # Underlined headers
            "fenced_code_block",  # ```code blocks```
        }

    @property
    def plugin_version(self) -> str:
        return "0.9.0"  # Beta version

    @property
    def minimum_api_version(self) -> str:
        return "1.0"  # Requires API v1.0

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract heading text from markdown nodes."""
        if node.type in {"atx_heading", "setext_heading"}:
            # Get the heading content (skip the # marks)
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            # Remove leading # and whitespace
            return content.lstrip("#").strip()
        if node.type == "fenced_code_block":
            # Try to get the language identifier
            for child in node.children:
                if child.type == "info_string":
                    return f"code:{source[child.start_byte:child.end_byte].decode('utf-8')}"
            return "code:unknown"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """Custom processing for markdown nodes."""
        chunk = super().process_node(node, source, file_path, parent_context)

        if chunk and node.type in {"atx_heading", "setext_heading"}:
            # Determine heading level
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if node.type == "atx_heading":
                level = len(content) - len(content.lstrip("#"))
                chunk.node_type = f"heading_level_{level}"
            else:
                # Setext headings are level 1 (===) or 2 (---)
                chunk.node_type = "heading_level_1"  # Simplified

        return chunk

    def should_include_chunk(self, chunk: CodeChunk) -> bool:
        """Custom filtering for markdown chunks."""
        # Always include headings regardless of size
        if chunk.node_type.startswith("heading"):
            return True

        # For code blocks, check minimum size
        if chunk.node_type.startswith("code:"):
            min_code_lines = self.config.custom_options.get("min_code_block_lines", 3)
            lines = chunk.end_line - chunk.start_line + 1
            return lines >= min_code_lines

        return super().should_include_chunk(chunk)


def demonstrate_custom_plugins():
    """Demonstrate using custom plugins."""
    print("=== Custom Plugin Demonstration ===\n")

    # Get the plugin manager
    manager = get_plugin_manager()

    # Register custom plugins
    print("1. Registering custom plugins...")
    manager.registry.register(GoPlugin)
    manager.registry.register(MarkdownPlugin)

    # Show plugin metadata
    go_plugin = manager.get_plugin("go")
    print("\nGo Plugin Metadata:")
    for key, value in go_plugin.plugin_metadata.items():
        print(f"  {key}: {value}")

    # Configure the Go plugin
    go_config = PluginConfig(
        chunk_types={
            "function_declaration",
            "method_declaration",
            "interface_declaration",
        },
        min_chunk_size=2,
        custom_options={"include_tests": False},
    )

    # Example: Process a hypothetical Go file
    print("\n2. Processing Go code (hypothetical)...")
    go_code = """
package main

import "fmt"

// Greeter interface defines greeting behavior
type Greeter interface {
    Greet(name string) string
}

// Person struct represents a person
type Person struct {
    Name string
    Age  int
}

// Greet implements the Greeter interface for Person
func (p Person) Greet(name string) string {
    return fmt.Sprintf("Hello %s, I'm %s", name, p.Name)
}

// TestGreeting is a test function (should be skipped)
func TestGreeting(t *testing.T) {
    // Test code here
}

func main() {
    person := Person{Name: "Alice", Age: 30}
    fmt.Println(person.Greet("Bob"))
}
"""

    # Note: This would work if we had the Go grammar installed
    print("  (Would process Go code if grammar was available)")

    # Configure markdown plugin
    md_config = PluginConfig(
        custom_options={
            "min_code_block_lines": 5,
            "include_yaml_frontmatter": True,
        },
    )

    # Example: Process a markdown file
    print("\n3. Processing Markdown (hypothetical)...")
    md_content = """
# Main Title

This is the introduction.

## Section 1

Content for section 1.

### Subsection 1.1

```python
def hello():
    print("Hello, world!")
```

## Section 2

More content here.
"""

    print("  (Would process Markdown if grammar was available)")

    # Show all registered languages
    print("\n4. All registered languages:")
    all_languages = manager.registry.list_languages()
    for lang in sorted(all_languages):
        plugin = manager.get_plugin(lang)
        print(f"  - {lang} (v{plugin.plugin_version})")

    # Show extension mappings
    print("\n5. File extension mappings:")
    extensions = manager.registry.list_extensions()
    for ext, lang in sorted(extensions.items()):
        print(f"  {ext} -> {lang}")


def demonstrate_plugin_loading():
    """Demonstrate loading plugins from a directory."""
    print("\n=== Plugin Directory Loading ===\n")

    # Create a custom plugins directory
    custom_dir = Path("custom_plugins")
    custom_dir.mkdir(exist_ok=True)

    # Save our custom plugin to a file
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

    # Load plugins from directory
    manager = get_plugin_manager()
    loaded = manager.load_plugins_from_directory(custom_dir)
    print(f"Loaded {loaded} plugin(s) from {custom_dir}")

    # Clean up
    plugin_file.unlink()
    custom_dir.rmdir()


if __name__ == "__main__":
    demonstrate_custom_plugins()
    demonstrate_plugin_loading()
