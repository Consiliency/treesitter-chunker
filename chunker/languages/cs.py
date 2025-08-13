from __future__ import annotations

from .base import LanguageConfig, language_config_registry


class CSharpConfig(LanguageConfig):
    """Language configuration for C# (csharp)."""

    @property
    def language_id(self) -> str:
        return "c_sharp"

    @property
    def name(self) -> str:
        # Canonical display name expected by tests
        return "csharp"

    @property
    def chunk_types(self) -> set[str]:
        # Common C# tree-sitter node types of interest
        return {
            "class_declaration",
            "struct_declaration",
            "interface_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
            "property_declaration",
            "field_declaration",
            "delegate_declaration",
            "record_declaration",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".cs", ".csx"}


# Register config with aliases so tests using "csharp" resolve
language_config_registry.register(CSharpConfig(), aliases=["csharp"])
