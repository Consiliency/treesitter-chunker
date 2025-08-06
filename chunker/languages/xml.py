"""XML language configuration."""

from typing import Any

from .base import LanguageConfig, language_config_registry
from .plugin_base import LanguagePlugin


class XMLPlugin(LanguagePlugin):
    """XML language plugin implementation."""

    @property
    def language_name(self) -> str:
        return "xml"

    @property
    def supported_node_types(self) -> set[str]:
        return {"document", "element", "self_closing_tag", "attribute", "cdata_section"}

    def get_chunk_type(self, node_type: str) -> str | None:
        return node_type if node_type in self.supported_node_types else None

    @staticmethod
    def extract_metadata(node: Any, source_code: bytes) -> dict[str, Any]:
        metadata = {"node_type": node.type}
        if node.type in {"element", "self_closing_tag"}:
            start_tag = node.child_by_field_name("start_tag") or node
            tag_name_node = (
                start_tag.child_by_field_name("name")
                if hasattr(start_tag, "child_by_field_name")
                else None
            )
            if tag_name_node:
                metadata["tag_name"] = source_code[
                    tag_name_node.start_byte : tag_name_node.end_byte
                ].decode("utf-8")
        return metadata


class XMLConfig(LanguageConfig):
    """XML language configuration."""

    @property
    def language_id(self) -> str:
        return "xml"

    @property
    def chunk_types(self) -> set[str]:
        """XML-specific chunk types."""
        return {"element", "self_closing_tag", "cdata_section"}

    @property
    def file_extensions(self) -> set[str]:
        return {".xml", ".xhtml", ".svg"}

    def __init__(self):
        super().__init__()
        self.add_ignore_type("text")
        self.add_ignore_type("comment")
        self.add_ignore_type("attribute_value")

    def is_chunk_node(self, node: Any, source: bytes) -> bool:
        """Override to add XML-specific logic."""
        if not super().is_chunk_node(node, source):
            return False
        return not (node.type == "element" and node.end_byte - node.start_byte < 50)


language_config_registry.register(XMLConfig())
