from .grammar_manager_contract import GrammarManagerContract


class GrammarManagerStub(GrammarManagerContract):
    """Stub implementation for grammar manager"""

    @staticmethod
    def add_grammar_source(_language: str, _repo_url: str) -> bool:
        """Stub returns False"""
        return False

    @staticmethod
    def fetch_grammars(_languages: list[str] | None = None) -> dict[str, bool]:
        """Stub returns empty dict"""
        return {}

    @staticmethod
    def compile_grammars(_languages: list[str] | None = None) -> dict[
        str,
        bool,
    ]:
        """Stub returns empty dict"""
        return {}

    @staticmethod
    def get_available_languages() -> set[str]:
        """Stub returns empty set"""
        return set()
