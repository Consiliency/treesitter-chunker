"""Tree-sitter grammar validator implementation."""

import logging
from pathlib import Path

from chunker.exceptions import ChunkerError
from chunker.interfaces.grammar import GrammarValidator

logger = logging.getLogger(__name__)


class ValidationError(ChunkerError):
    """Error during grammar validation."""


RETIREMENT_MESSAGE = (
    "TreeSitterGrammarValidator is retired (treesitter-chunker#400, "
    "treesitter-chunker#362): use "
    "chunker.grammar_management.core.GrammarValidator(cache_dir, "
    "trusted_artifacts=...) and its check_abi_compatibility(path, language) / "
    "validate_grammar(...), or chunker.grammar.integrity.probe_native_grammar"
)


class TreeSitterGrammarValidator(GrammarValidator):
    """Retired legacy validator (inventory V1).

    Its constructor never worked (it omitted ``LanguageRegistry.library_path``,
    treesitter-chunker#400), and it loaded grammars without native admission.
    The name stays importable until the next major version; constructing it
    and calling any instance method (reachable without the constructor, for
    example through a subclass) raise :class:`ValidationError` naming the
    replacement, and :meth:`check_abi_compatibility` performs no native load.
    """

    def __init__(self):
        """Raise: the class is retired."""
        raise ValidationError(RETIREMENT_MESSAGE)

    @staticmethod
    def check_abi_compatibility(grammar_path: Path) -> tuple[bool, str | None]:
        """Report retirement without loading ``grammar_path``.

        Returns:
            ``(False, <retirement message>)``
        """
        return False, RETIREMENT_MESSAGE

    def validate_node_types(
        self,
        language: str,
        expected_types: set[str],
    ) -> list[str]:
        """Validate expected node types exist.

        Retired: always raises :class:`ValidationError`.

        Args:
            language: Language name
            expected_types: Set of expected node type names

        Returns:
            List of missing node types
        """
        raise ValidationError(RETIREMENT_MESSAGE)

    def test_parse(self, language: str, sample_code: str) -> tuple[bool, str | None]:
        """Test parsing with sample code.

        Retired: always raises :class:`ValidationError`.

        Args:
            language: Language name
            sample_code: Sample code to parse

        Returns:
            Tuple of (success, error_message)
        """
        raise ValidationError(RETIREMENT_MESSAGE)

    def validate_grammar_features(self, language: str) -> dict[str, bool]:
        """Validate specific grammar features.

        Retired: always raises :class:`ValidationError`.

        Args:
            language: Language name

        Returns:
            Dictionary of feature -> supported
        """
        raise ValidationError(RETIREMENT_MESSAGE)

    def _collect_node_types(self, node, types: set[str]) -> None:
        """Recursively collect all node types in a tree."""
        if node.is_named:
            types.add(node.type)
        for child in node.children:
            self._collect_node_types(child, types)

    def _has_errors(self, node) -> bool:
        """Check if tree has any error nodes."""
        if node.type == "ERROR" or node.is_error:
            return True
        return any(self._has_errors(child) for child in node.children)

    def _find_error_nodes(self, node, errors=None):
        """Find all error nodes in tree."""
        if errors is None:
            errors = []
        if node.type == "ERROR" or node.is_error:
            errors.append(node)
        for child in node.children:
            self._find_error_nodes(child, errors)
        return errors

    @staticmethod
    def _get_minimal_test_code(language: str) -> str:
        """Get minimal valid code for a language."""
        minimal_code = {
            "python": "pass",
            "javascript": ";",
            "typescript": ";",
            "rust": "",
            "go": "package main",
            "ruby": "",
            "java": "class T{}",
            "c": "",
            "cpp": "",
            "csharp": "class T{}",
            "php": "<?php",
            "swift": "",
            "kotlin": "",
            "scala": "",
            "haskell": "",
            "lua": "",
            "bash": "",
            "json": "{}",
            "yaml": "---",
            "toml": "",
            "html": "<html></html>",
            "css": "",
            "sql": "SELECT 1",
            "markdown": "# Test",
        }
        return minimal_code.get(language, "")

    @staticmethod
    def _get_unicode_test_code(language: str) -> str | None:
        """Get unicode test code for a language."""
        unicode_tests = {
            "python": '# 你好\nx = "世界"',
            "javascript": '// 你好\nlet x = "世界";',
            "rust": """// 你好
let x = "世界";""",
            "go": """// 你好
var x = "世界\"""",
            "ruby": '# 你好\nx = "世界"',
            "java": """// 你好
String x = "世界";""",
        }
        return unicode_tests.get(language)

    @staticmethod
    def _get_critical_node_types(language: str) -> set[str]:
        """Get critical node types for a language."""
        critical_types = {
            "python": {"module", "function_definition", "class_definition"},
            "javascript": {"program", "function_declaration", "class_declaration"},
            "rust": {"source_file", "function_item", "struct_item"},
            "go": {"source_file", "function_declaration", "type_declaration"},
            "ruby": {"program", "method", "class"},
            "java": {"program", "method_declaration", "class_declaration"},
            "c": {"translation_unit", "function_definition", "struct_specifier"},
            "cpp": {"translation_unit", "function_definition", "class_specifier"},
        }
        return critical_types.get(language, set())
