
from .grammar_manager_contract import GrammarManagerContract


class GrammarManagerStub(GrammarManagerContract):
    """Stub implementation for grammar manager"""

    def add_grammar_source(self, _language: str, _repo_url: str) -> bool:
        """Stub returns False"""
        return False

    def fetch_grammars(self, _languages: list[str] | None = None) -> dict[str, bool]:
        """Stub returns empty dict"""
        return {}

    def compile_grammars(
        self,
        _languages: list[str] | None = None,
    ) -> dict[str, bool]:
        """Stub returns empty dict"""
        return {}

    def get_available_languages(self) -> set[str]:
        """Stub returns empty set"""
        return set()
