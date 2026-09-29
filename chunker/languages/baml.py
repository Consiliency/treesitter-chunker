"""Structural chunk selection for the pinned BAML grammar companion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import LanguageConfig, language_config_registry

if TYPE_CHECKING:
    from tree_sitter import Node


class BamlConfig(LanguageConfig):
    @property
    def language_id(self) -> str:
        return "baml"

    @property
    def file_extensions(self) -> set[str]:
        return {".baml"}

    @property
    def strict_parse(self) -> bool:
        return True

    @property
    def chunk_types(self) -> set[str]:
        return {
            "class_declaration",
            "enum_declaration",
            "interface_declaration",
            "implements_for_declaration",
            "function_declaration",
            "client_declaration",
            "generator_declaration",
            "retry_policy_declaration",
            "template_string_declaration",
            "type_alias_declaration",
            "test_declaration",
            "testset_declaration",
        }

    def get_definition_name(self, node: Node, source: bytes) -> str | None:
        if node.type != "implements_for_declaration":
            return None
        interface = node.child_by_field_name("interface")
        target = node.child_by_field_name("target")
        if interface is None or target is None:
            return None
        left = source[interface.start_byte : interface.end_byte].decode("utf-8")
        right = source[target.start_byte : target.end_byte].decode("utf-8")
        return f"{left} for {right}"


language_config_registry.register(BamlConfig())
