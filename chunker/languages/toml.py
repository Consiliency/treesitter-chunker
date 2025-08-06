"""TOML language configuration."""

from typing import Any

from .base import LanguageConfig, language_config_registry
from .plugin_base import LanguagePlugin


class TOMLPlugin(LanguagePlugin):
    """TOML language plugin implementation."""

    @property
    def language_name(self) -> str:
        return "toml"

    @property
    def supported_node_types(self) -> set[str]:
        return {"document", "table", "pair", "array", "inline_table"}

    def get_chunk_type(self, node_type: str) -> str | None:
        return node_type if node_type in self.supported_node_types else None

    @staticmethod
    def extract_metadata(node: Any, source_code: bytes) -> dict[str, Any]:
        metadata = {"node_type": node.type}
        if node.type == "pair":
            key_node = node.child_by_field_name("key")
            if key_node:
                metadata["key"] = source_code[
                    key_node.start_byte : key_node.end_byte
                ].decode("utf-8")
        elif node.type == "table":
            metadata["table_type"] = "standard"
        return metadata


class TOMLConfig(LanguageConfig):
    """TOML language configuration."""

    @property
    def language_id(self) -> str:
        return "toml"

    @property
    def chunk_types(self) -> set[str]:
        """TOML-specific chunk types."""
        return {"table", "pair", "array", "inline_table"}

    @property
    def file_extensions(self) -> set[str]:
        return {".toml"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("string")
        self.add_ignore_type("integer")
        self.add_ignore_type("float")
        self.add_ignore_type("boolean")
        self.add_ignore_type("comment")

    def is_chunk_node(self, node: Any, source: bytes) -> bool:
        """Override to add TOML-specific logic."""
        if not super().is_chunk_node(node, source):
            return False
        if node.type == "pair":
            parent = node.parent
            return parent and parent.type in {"document", "table"}
        return True


language_config_registry.register(TOMLConfig())
