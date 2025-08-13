"""
Support for Svelte language (Single File Components).
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


class SvelteConfig(LanguageConfig):
    """Language configuration for Svelte components."""

    @property
    def language_id(self) -> str:
        return "svelte"

    @property
    def chunk_types(self) -> set[str]:
        """Svelte-specific chunk types."""
        return {
            "script_element",
            "style_element",
            "template",
            "if_block",
            "each_block",
            "await_block",
            "key_block",
            "reactive_statement",
            "reactive_declaration",
            "store_subscription",
            "event_handler",
            "on_directive",
            "slot_element",
            "component",
            "fragment",
            "svelte_element",
            "svelte_component",
            "svelte_window",
            "svelte_body",
            "svelte_head",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".svelte"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"labeled_statement"},
                include_children=False,
                priority=6,
                metadata={"type": "reactive"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"transition_directive", "animation_directive"},
                include_children=False,
                priority=4,
                metadata={"type": "animation"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("text")


# Register the Svelte configuration


class SveltePlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Svelte component chunking."""

    @property
    def language_name(self) -> str:
        return "svelte"

    @property
    def supported_extensions(self) -> set[str]:
        return {".svelte"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "script_element",
            "style_element",
            "if_block",
            "each_block",
            "await_block",
            "key_block",
            "reactive_statement",
            "slot_element",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Svelte node."""
        if node.type == "script_element":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if 'context="module"' in content[:50]:
                return "module"
            return "instance"
        if node.type == "slot_element":
            for child in node.children:
                if child.type == "attribute" and "name=" in source[
                    child.start_byte : child.end_byte
                ].decode("utf-8"):
                    attr_content = source[child.start_byte : child.end_byte].decode(
                        "utf-8",
                    )
                    match = re.search(r'name="([^"]+)"', attr_content)
                    if match:
                        return match.group(1)
        elif node.type == "component":
            for child in node.children:
                if child.type == "tag_name":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Svelte."""
        chunks = []

        def extract_chunks(n: Node, in_script: bool = False, script_content: str = ""):
            if n.type == "script_element":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "context": (
                        "module" if 'context="module"' in content[:50] else "instance"
                    ),
                }
                if 'lang="ts"' in content[:50] or "lang='ts'" in content[:50]:
                    chunk["language"] = "typescript"
                else:
                    chunk["language"] = "javascript"
                chunks.append(chunk)

                # Extract reactive statements from script content
                script_text = content
                # Find the actual script content (between <script> tags)
                script_start = content.find(">") + 1 if ">" in content else 0
                script_end = (
                    content.rfind("</script>")
                    if "</script>" in content
                    else len(content)
                )
                script_body = (
                    content[script_start:script_end]
                    if script_start < script_end
                    else content
                )

                # Look for reactive statements
                lines = script_body.split("\n")
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("$:"):
                        reactive_chunk = {
                            "type": "reactive_statement",
                            "start_line": n.start_point[0] + 1 + i,
                            "end_line": n.start_point[0] + 1 + i,
                            "content": line,
                        }
                        chunks.append(reactive_chunk)

                in_script = True
                script_content = script_body
            elif n.type == "style_element":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                }
                if "global" in content[:50]:
                    chunk["is_global"] = True
                if 'lang="scss"' in content[:50] or "lang='scss'" in content[:50]:
                    chunk["preprocessor"] = "scss"
                elif 'lang="sass"' in content[:50] or "lang='sass'" in content[:50]:
                    chunk["preprocessor"] = "sass"
                elif 'lang="less"' in content[:50] or "lang='less'" in content[:50]:
                    chunk["preprocessor"] = "less"
                chunks.append(chunk)
            elif n.type in {"if_block", "each_block", "await_block", "key_block"}:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                }
                if n.type == "each_block":
                    match = re.search(r"{#each\\s+(\\w+)\\s+as\\s+(\\w+)", content)
                    if match:
                        chunk["array"] = match.group(1)
                        chunk["item"] = match.group(2)
                elif n.type == "await_block":
                    chunk["has_then"] = "{:then" in content
                    chunk["has_catch"] = "{:catch" in content
                chunks.append(chunk)
            elif n.type == "labeled_statement" and in_script:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                if content.strip().startswith("$:"):
                    chunk = {
                        "type": "reactive_statement",
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "content": content,
                        "is_reactive": True,
                    }
                    chunks.append(chunk)
            for child in n.children:
                extract_chunks(
                    child, in_script and n.type != "script_element", script_content
                )

        extract_chunks(node)
        # Fallback: scan raw source for control-flow markers when tree nodes aren't exposed
        try:
            text = source.decode("utf-8", errors="replace")
            lines = text.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("{#if"):
                    chunks.append(
                        {
                            "type": "if_block",
                            "start_line": i,
                            "end_line": i,
                            "content": line,
                        }
                    )
                elif stripped.startswith("{#each"):
                    chunks.append(
                        {
                            "type": "each_block",
                            "start_line": i,
                            "end_line": i,
                            "content": line,
                        }
                    )
                elif stripped.startswith("{#await"):
                    chunks.append(
                        {
                            "type": "await_block",
                            "start_line": i,
                            "end_line": i,
                            "content": line,
                        }
                    )
                elif stripped.startswith("{#key"):
                    chunks.append(
                        {
                            "type": "key_block",
                            "start_line": i,
                            "end_line": i,
                            "content": line,
                        }
                    )
        except Exception:
            pass
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Svelte-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type == "labeled_statement":
            return True
        if node.type == "element":
            for child in node.children:
                if child.type == "attribute" and any(
                    event
                    in (child.text.decode("utf-8") if hasattr(child, "text") else "")
                    for event in ["on:", "bind:", "use:"]
                ):
                    return len(node.children) > 5
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Guard against MockNode without byte attributes
        if not hasattr(node, "start_byte") or not hasattr(node, "end_byte"):
            return f"{node.type} (mock node)"

        # Handle elements that need content inspection
        if node.type in {"script_element", "style_element"}:
            return SveltePlugin._get_element_context(node, source)

        # Map block types
        block_context_map = {
            "if_block": "{#if} block",
            "each_block": "{#each} block",
            "await_block": "{#await} block",
            "key_block": "{#key} block",
            "reactive_statement": "$: reactive statement",
        }

        if node.type in block_context_map:
            return block_context_map[node.type]

        # Handle slot element
        if node.type == "slot_element":
            name = self.get_node_name(node, source)
            return f"<slot name='{name}'>" if name else "<slot>"

        return None

    @staticmethod
    def _get_element_context(node: Node, source: bytes) -> str:
        """Get context for script/style elements based on attributes."""
        # Guard against MockNode without byte attributes
        if not hasattr(node, "start_byte") or not hasattr(node, "end_byte"):
            return f"<{node.type}>"

        content = source[node.start_byte : node.end_byte].decode("utf-8")

        if node.type == "script_element":
            if 'context="module"' in content[:50]:
                return "<script context='module'>"
            return "<script>"
        if node.type == "style_element":
            if "global" in content[:50]:
                return "<style global>"
            return "<style>"

        return ""

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Svelte nodes with special handling for reactive features."""
        if node.type == "script_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                if 'context="module"' in content[:50]:
                    chunk.node_type = "module_script"
                    chunk.metadata = {"context": "module"}
                else:
                    chunk.node_type = "instance_script"
                    chunk.metadata = {"context": "instance"}
                if any(
                    store in content
                    for store in ["writable(", "readable(", "derived(", "$"]
                ):
                    chunk.metadata["uses_stores"] = True
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "labeled_statement":
            content = source[node.start_byte : node.end_byte].decode("utf-8")
            if content.strip().startswith("$:"):
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = "reactive_statement"
                    chunk.metadata = {
                        "reactive_type": "derived" if "=" in content else "effect",
                    }
                    return chunk if self.should_include_chunk(chunk) else None
        if node.type in {"if_block", "each_block", "await_block", "key_block"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                content = chunk.content
                chunk.metadata = {
                    "has_else": "{:else" in content or "{#else" in content,
                    "is_nested": parent_context is not None,
                }
                if node.type == "each_block":
                    chunk.metadata["has_key"] = "key" in content[:100]
                elif node.type == "await_block":
                    chunk.metadata["has_then"] = "{:then" in content
                    chunk.metadata["has_catch"] = "{:catch" in content
                return chunk if self.should_include_chunk(chunk) else None
        if node.type == "slot_element":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                name = self.get_node_name(node, source)
                chunk.metadata = {
                    "slot_name": name or "default",
                    "has_fallback": len(node.children) > 2,
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
        """Override to add semantic Svelte chunks alongside structural ones."""
        chunks = super().walk_tree(node, source, file_path, parent_context)

        # Merge in semantic chunks derived from content analysis
        try:
            semantic = self.get_semantic_chunks(node, source)
        except Exception:
            semantic = []

        if semantic:
            existing = {(c.node_type, c.content) for c in chunks}
            for sc in semantic:
                sc_type = sc.get("type")
                if sc_type in {
                    "reactive_statement",
                    "if_block",
                    "each_block",
                    "await_block",
                    "key_block",
                }:
                    content = sc.get("content", "")
                    if (sc_type, content) in existing:
                        continue
                    start_line = int(sc.get("start_line", 1))
                    end_line = int(sc.get("end_line", start_line))
                    chunk = CodeChunk(
                        language=self.language_name,
                        file_path=file_path,
                        node_type=sc_type,
                        start_line=start_line,
                        end_line=end_line,
                        byte_start=0,
                        byte_end=0,
                        parent_context=sc.get("context") or parent_context or "",
                        content=content,
                    )
                    chunks.append(chunk)

        return chunks
