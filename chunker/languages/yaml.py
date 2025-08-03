"""YAML language configuration."""
from typing import Any

from .base import LanguageConfig, language_config_registry
from .plugin_base import LanguagePlugin


class YAMLPlugin(LanguagePlugin):
    """YAML language plugin implementation."""

    @property
    def language_name(self) -> str:
        return "yaml"

    @property
    def supported_node_types(self) -> set[str]:
        return {"document", "block_mapping", "block_sequence",
            "block_mapping_pair", "flow_mapping", "flow_sequence"}

    def get_chunk_type(self, node_type: str) -> (str | None):
        return node_type if node_type in self.supported_node_types else None

    @staticmethod
    def extract_metadata(node: Any, source_code: bytes) -> dict[str, Any]:
        metadata = {"node_type": node.type}
        if node.type == "block_mapping_pair":
            key_node = node.child_by_field_name("key")
            if key_node:
                key_text = source_code[key_node.start_byte:key_node.end_byte
                    ].decode("utf-8").strip()
                metadata["key"] = key_text
        return metadata


class YAMLConfig(LanguageConfig):
    """YAML language configuration."""

    @property
    def language_id(self) -> str:
        return "yaml"

    @property
    def chunk_types(self) -> set[str]:
        """YAML-specific chunk types."""
        return {"block_mapping", "block_sequence", "block_mapping_pair",
            "flow_mapping", "flow_sequence"}

    @property
    def file_extensions(self) -> set[str]:
        return {".yaml", ".yml"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("plain_scalar")
        self.add_ignore_type("double_quote_scalar")
        self.add_ignore_type("single_quote_scalar")
        self.add_ignore_type("literal_scalar")
        self.add_ignore_type("folded_scalar")
        self.add_ignore_type("comment")
        self.add_ignore_type("anchor")
        self.add_ignore_type("alias")

    @staticmethod
    def is_chunk_node(node: Any, source: bytes) -> bool:
        """Override to add YAML-specific logic."""
        if not super().is_chunk_node(node, source):
            return False
        if node.type == "block_mapping_pair":
            parent = node.parent
            if parent and parent.type == "block_mapping":
                grandparent = parent.parent
                if grandparent and grandparent.type not in {"document",
                    "block_mapping_pair"}:
                    return False
        return True


language_config_registry.register(YAMLConfig(), aliases=["yml"])
