from pathlib import Path

from .template_generator_contract import TemplateGeneratorContract


class TemplateGeneratorStub(TemplateGeneratorContract):
    """Stub implementation for template generator"""

    def generate_plugin(
        self,
        language_name: str,
        _config: dict[str, any],
    ) -> tuple[bool, Path]:
        """Stub that returns success with fake path"""
        return (False, Path(f"chunker/languages/{language_name}.py"))

    def generate_test(
        self,
        language_name: str,
        _test_cases: list[dict[str, str]],
    ) -> tuple[bool, Path]:
        """Stub that returns success with fake path"""
        return (False, Path(f"tests/test_{language_name}_language.py"))

    def validate_plugin(self, _plugin_path: Path) -> tuple[bool, list[str]]:
        """Stub that returns not implemented"""
        return (False, ["Not implemented - Template Team will implement"])
