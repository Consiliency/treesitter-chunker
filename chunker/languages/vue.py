"""
Support for Vue language (Single File Components).
"""

from __future__ import annotations

import re

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class VueConfig(LanguageConfig):
    """Language configuration for Vue Single File Components."""

    @property
    def language_id(self) -> str:
        return "vue"

    @property
    def chunk_types(self) -> set[str]:
        """Vue-specific chunk types."""
        return {
            # Vue SFC sections
            "template_element",
            "script_element",
            "style_element",
            # Component definitions
            "component_definition",
            "export_statement",
            # Vue 3 Composition API
            "setup_function",
            "ref_declaration",
            "reactive_declaration",
            "computed_property",
            "watch_expression",
            # Options API
            "data_property",
            "methods_property",
            "computed_properties",
            "props_definition",
            "emits_definition",
            # Lifecycle hooks
            "lifecycle_hook",
            "mounted_hook",
            "created_hook",
            "updated_hook",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".vue"}

    def __init__(self):
        super().__init__()

        # Add rules for template directives
        self.add_chunk_rule(
            ChunkRule(
                node_types={"v_if", "v_for", "v_show"},
                include_children=True,
                priority=5,
                metadata={"type": "directive"},
            ),
        )

        # Add rules for slots
        self.add_chunk_rule(
            ChunkRule(
                node_types={"slot_element", "template_slot"},
                include_children=False,
                priority=4,
                metadata={"type": "slot"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("text")


# Register the Vue configuration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


# Plugin implementation for backward compatibility
class VuePlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Vue Single File Component chunking."""

    @property
    def language_name(self) -> str:
        return "vue"

    @property
    def supported_extensions(self) -> set[str]:
        return {".vue"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "template_element",
            "script_element",
            "style_element",
            "component_definition",
            "export_statement",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Vue node."""
        # For script exports
        if node.type == "export_statement":
            # Look for default export with component name
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "name:" in content:
                # Extract component name from options

                match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
        # For component definitions
        elif node.type == "component_definition":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Vue SFCs."""
        chunks = []

        def extract_chunks(n: Node, section: str | None = None):
            # Handle main SFC sections
            if n.type in {"template_element", "script_element", "style_element"}:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "section": n.type.replace("_element", ""),
                }

                # Check for attributes
                if n.type == "script_element":
                    if "setup" in content[:50]:
                        chunk["is_setup"] = True
                    if 'lang="ts"' in content[:50] or "lang='ts'" in content[:50]:
                        chunk["language"] = "typescript"
                    else:
                        chunk["language"] = "javascript"
                elif n.type == "style_element":
                    if "scoped" in content[:50]:
                        chunk["is_scoped"] = True
                    if 'lang="scss"' in content[:50] or "lang='scss'" in content[:50]:
                        chunk["preprocessor"] = "scss"
                    elif 'lang="sass"' in content[:50] or "lang='sass'" in content[:50]:
                        chunk["preprocessor"] = "sass"
                    elif 'lang="less"' in content[:50] or "lang='less'" in content[:50]:
                        chunk["preprocessor"] = "less"

                chunks.append(chunk)
                section = n.type

            # Handle component exports
            elif n.type == "export_statement" and section == "script_element":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                if "export default" in content:
                    chunk = {
                        "type": "component_definition",
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "content": content,
                        "name": self.get_node_name(n, source),
                    }

                    # Detect Vue version and API style
                    if "setup()" in content or "defineComponent" in content:
                        chunk["api_style"] = "composition"
                        chunk["vue_version"] = 3
                    else:
                        chunk["api_style"] = "options"
                        chunk["vue_version"] = 2

                    chunks.append(chunk)

            # Continue traversal
            for child in n.children:
                extract_chunks(child, section)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Vue-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All main SFC sections should be chunked
        if node.type in {"template_element", "script_element", "style_element"}:
            return True
        # Component definitions
        if node.type == "export_statement":
            # Need to check if it's export default
            return True
        # Template directives with complex content
        if node.type in {"element", "template"}:
            # Check for v-if, v-for attributes
            for child in node.children:
                if child.type == "attribute" and any(
                    attr in child.text.decode("utf-8") if hasattr(child, "text") else ""
                    for attr in ["v-if", "v-for", "v-show"]
                ):
                    return len(node.children) > 3
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type == "template_element":
            return "<template> section"
        if node.type == "script_element":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "setup" in content[:50]:
                return "<script setup> section"
            return "<script> section"
        if node.type == "style_element":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "scoped" in content[:50]:
                return "<style scoped> section"
            return "<style> section"
        if node.type == "component_definition":
            return f"Component {name}" if name else "Component definition"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Vue nodes with special handling for SFC structure."""
        # Handle template section with special parsing
        if node.type == "template_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                # Extract template content without tags
                content = chunk.content

                template_match = re.search(
                    r"<template[^>]*>(.*)</template>",
                    content,
                    re.DOTALL,
                )
                if template_match:
                    chunk.metadata = {
                        "template_content": template_match.group(1).strip(),
                        "has_slots": "slot" in content,
                    }
                return chunk if self.should_include_chunk(chunk) else None

        # Handle script section
        if node.type == "script_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                chunk.metadata = {
                    "is_setup": "setup" in content[:50],
                    "uses_typescript": 'lang="ts"' in content[:50]
                    or "lang='ts'" in content[:50],
                }
                # Detect Composition API usage
                if any(
                    api in content
                    for api in ["ref(", "reactive(", "computed(", "watch("]
                ):
                    chunk.metadata["uses_composition_api"] = True
                return chunk if self.should_include_chunk(chunk) else None

        # Handle style section
        if node.type == "style_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                chunk.metadata = {
                    "is_scoped": "scoped" in content[:50],
                    "preprocessor": self._detect_style_preprocessor(content),
                }
                return chunk if self.should_include_chunk(chunk) else None

        # Handle component exports
        if node.type == "export_statement":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "export default" in content:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = "component_definition"
                    chunk.metadata = {
                        "component_name": self.get_node_name(node, source),
                        "has_props": "props:" in content or "defineProps" in content,
                        "has_emits": "emits:" in content or "defineEmits" in content,
                    }
                    return chunk if self.should_include_chunk(chunk) else None

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

    def _detect_style_preprocessor(self, content: str) -> str | None:
        """Detect the style preprocessor from style tag attributes."""
        if 'lang="scss"' in content[:50] or "lang='scss'" in content[:50]:
            return "scss"
        if 'lang="sass"' in content[:50] or "lang='sass'" in content[:50]:
            return "sass"
        if 'lang="less"' in content[:50] or "lang='less'" in content[:50]:
            return "less"
        if 'lang="stylus"' in content[:50] or "lang='stylus'" in content[:50]:
            return "stylus"
        return None
