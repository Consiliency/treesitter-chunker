"""Rust language configuration for tree-sitter chunking."""

from .base import LanguageConfig, language_config_registry


class RustConfig(LanguageConfig):
    """Language configuration for Rust."""

    @property
    def language_id(self) -> str:
        return "rust"

    @property
    def chunk_types(self) -> set[str]:
        """Rust-specific chunk types."""
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
            "foreign_mod_item",
            "union_item",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".rs"}


# Create and register the Rust configuration if not already present
rust_config = RustConfig()
if language_config_registry.get("rust") is None:
    language_config_registry.register(rust_config)
