from typing import Optional

from tree_sitter import Node

from .language_plugin_contract import ExtendedLanguagePluginContract


class ExtendedLanguagePluginStub(ExtendedLanguagePluginContract):
    """Stub for language plugin testing"""

    def get_semantic_chunks(self, _node: Node, _source: bytes) -> list[dict[str, any]]:
        """Returns empty list"""
        return []

    def get_chunk_node_types(self) -> set[str]:
        """Returns minimal set"""
        return {"function_definition"}

    def should_chunk_node(self, _node: Node) -> bool:
        """Always returns False"""
        return False

    def get_node_context(self, _node: Node, _source: bytes) -> Optional[str]:
        """Returns None"""
        return None
