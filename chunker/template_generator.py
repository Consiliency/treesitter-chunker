"""Template-based generator for language plugins and tests.

This module implements the TemplateGeneratorContract to generate language plugin
files and test files from Jinja2 templates.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .contracts.template_generator_contract import TemplateGeneratorContract


class TemplateGenerator(TemplateGeneratorContract):
    """Generate language plugin and test files from templates."""

    def __init__(self, template_dir: Path | None = None):
        """Initialize the template generator.

        Args:
            template_dir: Directory containing templates. Defaults to templates/ in package.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent.parent / "templates"
        self.template_dir = template_dir
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def generate_plugin(
        self,
        language_name: str,
        config: dict[str, any],
    ) -> tuple[bool, Path]:
        """Generate a language plugin file from template.

        Args:
            language_name: Name of the language (e.g., 'css', 'html')
            config: Configuration including node types, file extensions, etc.

        Returns:
            Tuple of (success, path to generated file)
        """
        if not self._validate_language_name(language_name):
            return False, Path()
        if not self._validate_config(config):
            return False, Path()
        template_vars = self._prepare_plugin_variables(language_name, config)
        try:
            template = self._env.get_template("language_plugin.py.j2")
            content = template.render(**template_vars)
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"Error rendering template: {e}")
            return False, Path()
        output_path = (
            Path(
                __file__,
            ).parent
            / "languages"
            / f"{language_name}.py"
        )
        try:
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"Error writing file: {e}")
            return False, Path()
        return True, output_path

    def generate_test(
        self,
        language_name: str,
        test_cases: list[dict[str, str]],
    ) -> tuple[bool, Path]:
        """Generate test file for a language plugin.

        Args:
            language_name: Name of the language
            test_cases: List of test case definitions

        Returns:
            Tuple of (success, path to generated test file)
        """
        if not self._validate_language_name(language_name):
            return False, Path()
        if not self._validate_test_cases(test_cases):
            return False, Path()
        plugin_path = (
            Path(
                __file__,
            ).parent
            / "languages"
            / f"{language_name}.py"
        )
        if not plugin_path.exists():
            print(f"Plugin for {language_name} does not exist")
            return False, Path()
        template_vars = self._prepare_test_variables(language_name, test_cases)
        try:
            template = self._env.get_template("language_test.py.j2")
            content = template.render(**template_vars)
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"Error rendering template: {e}")
            return False, Path()
        output_path = (
            Path(
                __file__,
            ).parent.parent
            / "tests"
            / f"test_{language_name}_language.py"
        )
        try:
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        except (FileNotFoundError, OSError, ValueError) as e:
            print(f"Error writing file: {e}")
            return False, Path()
        return True, output_path

    @staticmethod
    def validate_plugin(plugin_path: Path) -> tuple[bool, list[str]]:
        """Validate a generated plugin file.

        Args:
            plugin_path: Path to plugin file

        Returns:
            Tuple of (is_valid, list of issues if any)
        """
        issues = []
        if not plugin_path.exists():
            return False, ["Plugin file does not exist"]
        if not plugin_path.is_file():
            return False, ["Plugin path is not a file"]
        try:
            content = plugin_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as e:
            return False, [f"Could not read file: {e}"]
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
        required_imports = [
            "from tree_sitter import Node",
            "from .plugin_base import LanguagePlugin",
            "from ..contracts.language_plugin_contract import ExtendedLanguagePluginContract",
        ]
        issues.extend(
            f"Missing required import: {imp}"
            for imp in required_imports
            if imp not in content
        )
        class_pattern = (
            "class \\w+Plugin\\(.*LanguagePlugin.*ExtendedLanguagePluginContract.*\\):"
        )
        if not re.search(class_pattern, content):
            issues.append(
                "Plugin class must inherit from both LanguagePlugin and ExtendedLanguagePluginContract",
            )
        required_methods = [
            "get_semantic_chunks",
            "get_chunk_node_types",
            "should_chunk_node",
            "get_node_context",
            "language_name",
            "supported_extensions",
            "default_chunk_types",
            "get_node_name",
        ]
        issues.extend(
            f"Missing required method: {method}"
            for method in required_methods
            if f"def {method}" not in content and f"def {method}(" not in content
        )
        return len(issues) == 0, issues

    @staticmethod
    def _validate_language_name(name: str) -> bool:
        """Validate language name is lowercase alphanumeric."""
        return bool(re.match(r"^[a-z0-9]+$", name))

    @staticmethod
    def _validate_config(config: dict[str, any]) -> bool:
        """Validate config has required fields."""
        return "node_types" in config and "file_extensions" in config

    @staticmethod
    def _validate_test_cases(test_cases: list[dict[str, str]]) -> bool:
        """Validate test cases have required fields."""
        if not test_cases:
            return False
        for case in test_cases:
            if "name" not in case or "code" not in case:
                return False
        return True

    @staticmethod
    def _prepare_plugin_variables(
        language_name: str,
        config: dict[str, any],
    ) -> dict[str, any]:
        """Prepare variables for plugin template rendering."""
        class_name = language_name.capitalize()
        file_extensions = [
            (ext if ext.startswith(".") else f".{ext}")
            for ext in config["file_extensions"]
        ]
        return {
            "language_name": language_name,
            "class_name": class_name,
            "node_types": config["node_types"],
            "file_extensions": file_extensions,
            "include_imports": config.get("include_imports", True),
            "include_decorators": config.get("include_decorators", False),
            "include_nested": config.get("include_nested", True),
            "custom_node_handling": config.get("custom_node_handling", {}),
        }

    @staticmethod
    def _prepare_test_variables(
        language_name: str,
        test_cases: list[dict[str, str]],
    ) -> dict[str, any]:
        """Prepare variables for test template rendering."""
        class_name = language_name.capitalize()
        processed_cases = [
            {
                "name": case["name"],
                "code": case["code"],
                "expected_chunks": case.get("expected_chunks", 1),
                "expected_types": case.get("expected_types", []),
            }
            for case in test_cases
        ]
        return {
            "language_name": language_name,
            "class_name": class_name,
            "test_cases": processed_cases,
        }
