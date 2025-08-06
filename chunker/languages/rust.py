from __future__ import annotations

from typing import TYPE_CHECKING

from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class RustPlugin(LanguagePlugin):
    """Plugin for Rust language chunking."""

    @property
    def language_name(self) -> str:
        return "rust"

    @property
    def supported_extensions(self) -> set[str]:
        return {".rs"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "function_item",
            "impl_item",
            "trait_item",
            "struct_item",
            "enum_item",
            "mod_item",
            "macro_definition",
            "const_item",
            "static_item",
            "type_item",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a Rust node."""
        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        name = self.get_node_name(node, chunk.content.encode("utf-8"))
        if not name:
            return chunk.parent_context
        if node.type == "impl_item":
            impl_type = None
            for child in node.children:
                if child.type in {
                    "type_identifier",
                    "generic_type",
                    "reference_type",
                    "pointer_type",
                }:
                    impl_type = chunk.content.encode("utf-8")[
                        child.start_byte : child.end_byte
                    ].decode("utf-8")
                    break
            if impl_type:
                name = f"impl {impl_type}"
        if chunk.parent_context:
            return f"{chunk.parent_context}::{name}"
        return name

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Rust nodes with special handling."""
        if node.type == "function_item" and not self.config.custom_options.get(
            "include_tests",
            True,
        ):
            prev_sibling = node.prev_named_sibling
            if prev_sibling and prev_sibling.type == "attribute_item":
                attr_content = source[
                    prev_sibling.start_byte : prev_sibling.end_byte
                ].decode("utf-8")
                if "#[test]" in attr_content or "#[cfg(test)]" in attr_content:
                    return None
        visibility = ""
        for child in node.children:
            if child.type == "visibility_modifier":
                visibility = (
                    source[child.start_byte : child.end_byte].decode("utf-8") + " "
                )
                break
        chunk = self.create_chunk(node, source, file_path, parent_context)
        if chunk and self.should_include_chunk(chunk):
            if visibility and visibility.strip() in {"pub", "pub(crate)", "pub(super)"}:
                chunk.node_type = f"{visibility.strip()}_{chunk.node_type}"
            return chunk
        return None
