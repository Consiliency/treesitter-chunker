"""
Support for Vue language (Single File Components).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.types import CodeChunk

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node

# Content preview length for detecting lang attributes in SFC templates
CONTENT_PREVIEW_LENGTH = 50

# Supported script languages
SCRIPT_LANGUAGES = frozenset({"ts", "typescript"})

# Supported style languages
STYLE_LANGUAGES = frozenset({"scss", "sass", "less", "stylus"})


class VueConfig(LanguageConfig):
    """Language configuration for Vue Single File Components."""

    @property
    def language_id(self) -> str:
        return "vue"

    @property
    def chunk_types(self) -> set[str]:
        """Vue-specific chunk types."""
        return {
            "template_element",
            "script_element",
            "style_element",
            "component_definition",
            "export_statement",
            "setup_function",
            "ref_declaration",
            "reactive_declaration",
            "computed_property",
            "watch_expression",
            "data_property",
            "methods_property",
            "computed_properties",
            "props_definition",
            "emits_definition",
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
        self.add_chunk_rule(
            ChunkRule(
                node_types={
                    "v_if",
                    "v_for",
                    "v_show",
                },
                include_children=True,
                priority=5,
                metadata={"type": "directive"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"slot_element", "template_slot"},
                include_children=False,
                priority=4,
                metadata={"type": "slot"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("text")


# Register the Vue configuration


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

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Vue node."""
        if node.type == "export_statement":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if "name:" in content:
                match = re.search(
                    r'name:\\s*[\'\\"]([^\'\\"]+)[\'\\"]',
                    content,
                )
                if match:
                    return match.group(1)
        elif node.type == "component_definition":
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Vue SFCs."""
        chunks = []

        def extract_chunks(n: Node, section: str | None = None):
            if n.type in {
                "template_element",
                "script_element",
                "style_element",
            }:
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
                if n.type == "script_element":
                    preview = content[:CONTENT_PREVIEW_LENGTH]
                    if "setup" in preview:
                        chunk["is_setup"] = True
                    script_lang = self._detect_script_lang(content)
                    chunk["language"] = "typescript" if script_lang else "javascript"
                    # Heuristic: raw_text script contents are not parsed into JS AST.
                    # Detect component definition directly from the script text.
                    if ("export default" in content) or ("defineComponent" in content):
                        comp = {
                            "type": "component_definition",
                            "start_line": n.start_point[0] + 1,
                            "end_line": n.end_point[0] + 1,
                            "content": content,
                            "name": None,
                        }
                        # Try to extract a component name
                        name_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", content)
                        if not name_match:
                            name_match = re.search(
                                r"defineComponent\(\s*\{[^}]*name:\s*['\"]([^'\"]+)['\"]",
                                content,
                                re.DOTALL,
                            )
                        if name_match:
                            comp["name"] = name_match.group(1)
                        chunks.append(comp)
                elif n.type == "style_element":
                    preview = content[:CONTENT_PREVIEW_LENGTH]
                    if "scoped" in preview:
                        chunk["is_scoped"] = True
                    style_lang = self._detect_style_lang(content)
                    if style_lang:
                        chunk["preprocessor"] = style_lang
                chunks.append(chunk)
                section = n.type
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
        if node.type in {
            "template_element",
            "script_element",
            "style_element",
        }:
            return True
        if node.type == "export_statement":
            return True
        if node.type in {"element", "template"}:
            for child in node.children:
                if child.type == "attribute" and any(
                    attr in child.text.decode("utf-8") if hasattr(child, "text") else ""
                    for attr in ["v-if", "v-for", "v-show"]
                ):
                    return len(node.children) > 3
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Handle special elements that need content inspection
        if node.type in {"script_element", "style_element"}:
            return VuePlugin._get_element_context(node, source)

        # Map node types to their context
        node_context_map = {
            "template_element": "<template> section",
            "component_definition": None,  # Special handling needed
        }

        if node.type not in node_context_map and node.type not in {
            "script_element",
            "style_element",
        }:
            return None

        if node.type == "component_definition":
            name = self.get_node_name(node, source)
            return f"Component {name}" if name else "Component definition"

        return node_context_map.get(node.type)

    @staticmethod
    def _get_element_context(node: Node, source: bytes) -> str:
        """Get context for script/style elements based on attributes."""
        content = source[node.start_byte : node.end_byte].decode("utf-8")
        preview = content[:CONTENT_PREVIEW_LENGTH]

        if node.type == "script_element":
            if "setup" in preview:
                return "<script setup> section"
            return "<script> section"
        if node.type == "style_element":
            if "scoped" in preview:
                return "<style scoped> section"
            return "<style> section"

        return ""

    def _detect_script_lang(self, content: str) -> str | None:
        """Detect script language from SFC content.

        Args:
            content: Full file content.

        Returns:
            Detected language or None.
        """
        preview = content[:CONTENT_PREVIEW_LENGTH]
        for lang in SCRIPT_LANGUAGES:
            if f'lang="{lang}"' in preview or f"lang='{lang}'" in preview:
                return lang
        return None

    def _detect_style_lang(self, content: str) -> str | None:
        """Detect style language from SFC content.

        Args:
            content: Full file content.

        Returns:
            Detected language or None.
        """
        preview = content[:CONTENT_PREVIEW_LENGTH]
        for lang in STYLE_LANGUAGES:
            if f'lang="{lang}"' in preview or f"lang='{lang}'" in preview:
                return lang
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Vue nodes with special handling for SFC structure."""
        if node.type == "template_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
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
        if node.type == "script_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                preview = content[:CONTENT_PREVIEW_LENGTH]
                chunk.metadata = {
                    "is_setup": "setup" in preview,
                    "uses_typescript": self._detect_script_lang(content) is not None,
                }
                if any(
                    api in content
                    for api in ["ref(", "reactive(", "computed(", "watch("]
                ):
                    chunk.metadata["uses_composition_api"] = True
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "style_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                preview = content[:CONTENT_PREVIEW_LENGTH]
                chunk.metadata = {
                    "is_scoped": "scoped" in preview,
                    "preprocessor": self._detect_style_lang(content),
                }
                return chunk if self.should_include_chunk(chunk) else None
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
        return super().process_node(node, source, file_path, parent_context)

    def walk_tree(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> list[CodeChunk]:
        """Override to add semantic Vue chunks in addition to structural ones.

        The Vue grammar often treats script/style contents as raw_text without
        nested JavaScript/CSS nodes. We supplement structural chunks with
        semantic ones like component_definition by scanning script contents.
        """
        # First, collect the default structural chunks
        chunks = super().walk_tree(node, source, file_path, parent_context)

        # Then, add semantic chunks derived from content
        try:
            semantic = self.get_semantic_chunks(node, source)
        except Exception:
            semantic = []

        if semantic:
            # Avoid duplicates by content and type
            existing = {(c.node_type, c.content) for c in chunks}
            for sc in semantic:
                sc_type = sc.get("type")
                if sc_type == "component_definition":
                    content = sc.get("content", "")
                    if (sc_type, content) in existing:
                        continue
                    start_line = int(sc.get("start_line", 1))
                    end_line = int(sc.get("end_line", start_line))
                    chunk = CodeChunk(
                        language=self.language_name,
                        file_path=file_path,
                        node_type="component_definition",
                        start_line=start_line,
                        end_line=end_line,
                        byte_start=0,
                        byte_end=0,
                        parent_context="script_element",
                        content=content,
                    )
                    name = sc.get("name")
                    if name:
                        chunk.metadata["component_name"] = name
                    chunks.append(chunk)

        return chunks
