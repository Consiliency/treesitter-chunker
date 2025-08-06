from abc import ABC, abstractmethod
from pathlib import Path


class TemplateGeneratorContract(ABC):
    """Contract for generating language plugin and test files"""

    @staticmethod
    @abstractmethod
    def generate_plugin(
        language_name: str,
        config: dict[str, any],
    ) -> tuple[bool, Path]:
        """Generate a language plugin file from template

        Args:
            language_name: Name of the language (e.g., 'css', 'html')
            config: Configuration including node types, file extensions, etc.

        Returns:
            Tuple of (success, path to generated file)

        Preconditions:
            - language_name must be lowercase alphanumeric
            - config must contain 'node_types' and 'file_extensions'

        Postconditions:
            - Plugin file created at chunker/languages/{language_name}.py
            - File contains valid Python code following plugin pattern
        """

    @staticmethod
    @abstractmethod
    def generate_test(
        language_name: str,
        test_cases: list[dict[str, str]],
    ) -> tuple[bool, Path]:
        """Generate test file for a language plugin

        Args:
            language_name: Name of the language
            test_cases: List of test case definitions

        Returns:
            Tuple of (success, path to generated test file)

        Preconditions:
            - language_name must match an existing plugin
            - test_cases must contain 'name' and 'code' fields

        Postconditions:
            - Test file created at tests/test_{language_name}_language.py
            - Contains runnable pytest test cases
        """

    @staticmethod
    @abstractmethod
    def validate_plugin(plugin_path: Path) -> tuple[bool, list[str]]:
        """Validate a generated plugin file

        Args:
            plugin_path: Path to plugin file

        Returns:
            Tuple of (is_valid, list of issues if any)

        Preconditions:
            - plugin_path must exist and be readable

        Postconditions:
            - No side effects, purely validation
        """
