from tree_sitter import Node

from .language_plugin_contract import ExtendedLanguagePluginContract


class ExtendedLanguagePluginStub(ExtendedLanguagePluginContract):
    """Stub for language plugin testing"""

    @staticmethod
    def get_semantic_chunks(_node: Node, _source: bytes) -> list[dict[str, any]]:
        """Returns empty list"""
        return []

    @staticmethod
    def get_chunk_node_types() -> set[str]:
        """Returns minimal set"""
        return {"function_definition"}

    @staticmethod
    def should_chunk_node(_node: Node) -> bool:
        """Always returns False"""
        return False

    @staticmethod
    def get_node_context(_node: Node, _source: bytes) -> str | None:
        """Returns None"""
        return None
