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
        return {"template_element", "script_element", "style_element",
            "component_definition", "export_statement", "setup_function",
            "ref_declaration", "reactive_declaration", "computed_property",
            "watch_expression", "data_property", "methods_property",
            "computed_properties", "props_definition", "emits_definition",
            "lifecycle_hook", "mounted_hook", "created_hook", "updated_hook"}

    @property
    def file_extensions(self) -> set[str]:
        return {".vue"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(ChunkRule(node_types={"v_if", "v_for", "v_show",
            }, include_children=True, priority=5, metadata={"type":
            "directive"}))
        self.add_chunk_rule(ChunkRule(node_types={"slot_element",
            "template_slot"}, include_children=False, priority=4, metadata={"type": "slot"}))
        self.add_ignore_type("comment")
        self.add_ignore_type("text")


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


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
        return {"template_element", "script_element", "style_element",
            "component_definition", "export_statement"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract the name from a Vue node."""
        if node.type == "export_statement":
            content = source[node.start_byte:node.end_byte].decode("utf-8")
            if "name:" in content:
                match = re.search(r'name:\\s*[\'\\"]([^\'\\"]+)[\'\\"]', content,
                    )
                if match:
                    return match.group(1)
        elif node.type == "component_definition":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Vue SFCs."""
        chunks = []

        def extract_chunks(n: Node, section: (str | None) = None):
            if n.type in {"template_element", "script_element", "style_element",
                }:
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": n.type, "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1, "content": content,
                    "section": n.type.replace("_element", "")}
                if n.type == "script_element":
                    if "setup" in content[:50]:
                        chunk["is_setup"] = True
                    if 'lang="ts"' in content[:50] or "lang='ts'" in content[:
                        50]:
                        chunk["language"] = "typescript"
                    else:
                        chunk["language"] = "javascript"
                elif n.type == "style_element":
                    if "scoped" in content[:50]:
                        chunk["is_scoped"] = True
                    if 'lang="scss"' in content[:50
                        ] or "lang='scss'" in content[:50]:
                        chunk["preprocessor"] = "scss"
                    elif 'lang="sass"' in content[:50
                        ] or "lang='sass'" in content[:50]:
                        chunk["preprocessor"] = "sass"
                    elif 'lang="less"' in content[:50
                        ] or "lang='less'" in content[:50]:
                        chunk["preprocessor"] = "less"
                chunks.append(chunk)
                section = n.type
            elif n.type == "export_statement" and section == "script_element":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                if "export default" in content:
                    chunk = {"type": "component_definition", "start_line":
                        n.start_point[0] + 1, "end_line": n.end_point[0] +
                        1, "content": content, "name": self.get_node_name(n,
                        source)}
                    if "setup()" in content or "defineComponent" in content:
                        chunk["api_style"] = "composition"
                        chunk["vue_version"] = 3
                    else:
                        chunk["api_style"] = "options"
                        chunk["vue_version"] = 2
                    chunks.append(chunk)
            for child in n.children:
                extract_chunks(child, section)
        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Vue-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in {"template_element", "script_element", "style_element",
            }:
            return True
        if node.type == "export_statement":
            return True
        if node.type in {"element", "template"}:
            for child in node.children:
                if child.type == "attribute" and any(attr in child.text.
                    decode("utf-8") if hasattr(child, "text") else "" for
                    attr in ["v-if", "v-for", "v-show"]):
                    return len(node.children) > 3
        return False

    def get_node_context(self, node: Node, source: bytes) -> (str | None):
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)
        if node.type == "template_element":
            return "<template> section"
        if node.type == "script_element":
            content = source[node.start_byte:node.end_byte].decode("utf-8")
            if "setup" in content[:50]:
                return "<script setup> section"
            return "<script> section"
        if node.type == "style_element":
            content = source[node.start_byte:node.end_byte].decode("utf-8")
            if "scoped" in content[:50]:
                return "<style scoped> section"
            return "<style> section"
        if node.type == "component_definition":
            return f"Component {name}" if name else "Component definition"
        return None

    def process_node(self, node: Node, source: bytes, file_path: str,
        parent_context: (str | None) = None):
        """Process Vue nodes with special handling for SFC structure."""
        if node.type == "template_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                template_match = re.search(r"<template[^>]*>(.*)</template>",
                    content, re.DOTALL)
                if template_match:
                    chunk.metadata = {"template_content": template_match.
                        group(1).strip(), "has_slots": "slot" in content}
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "script_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                chunk.metadata = {"is_setup": "setup" in content[:50],
                    "uses_typescript": 'lang="ts"' in content[:50] or
                    "lang='ts'" in content[:50]}
                if any(api in content for api in ["ref(", "reactive(",
                    "computed(", "watch("]):
                    chunk.metadata["uses_composition_api"] = True
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "style_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                chunk.metadata = {"is_scoped": "scoped" in content[:50],
                    "preprocessor": self._detect_style_preprocessor(content)}
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "export_statement":
            content = source[node.start_byte:node.end_byte].decode("utf-8")
            if "export default" in content:
                chunk = self.create_chunk(node, source, file_path,
                    parent_context)
                if chunk:
                    chunk.node_type = "component_definition"
                    chunk.metadata = {"component_name": self.get_node_name(
                        node, source), "has_props": "props:" in content or
                        "defineProps" in content, "has_emits": "emits:" in
                        content or "defineEmits" in content}
                    return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)

    @staticmethod
    def _detect_style_preprocessor(content: str) -> (str | None):
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
