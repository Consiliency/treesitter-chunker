"""Concrete stub implementation for testing - Grammar Discovery"""

from datetime import datetime

from .discovery_contract import (
    GrammarCompatibility,
    GrammarDiscoveryContract,
    GrammarInfo,
)


class GrammarDiscoveryStub(GrammarDiscoveryContract):
    """Stub implementation that can be instantiated and tested"""

    def list_available_grammars(
        self,
        include_community: bool = False,
    ) -> list[GrammarInfo]:
        """Stub that returns valid default values"""
        # Return a minimal list for testing
        return [
            GrammarInfo(
                name="python",
                url="https://github.com/tree-sitter/tree-sitter-python",
                version="0.20.0",
                last_updated=datetime(2023, 1, 1),
                stars=500,
                description="Python grammar for tree-sitter",
                supported_extensions=[".py", ".pyw"],
                official=True,
            ),
            GrammarInfo(
                name="rust",
                url="https://github.com/tree-sitter/tree-sitter-rust",
                version="0.20.0",
                last_updated=datetime(2023, 1, 1),
                stars=400,
                description="Rust grammar for tree-sitter",
                supported_extensions=[".rs"],
                official=True,
            ),
        ]

    def get_grammar_info(self, language: str) -> GrammarInfo | None:
        """Stub that returns info for known languages"""
        if language == "python":
            return GrammarInfo(
                name="python",
                url="https://github.com/tree-sitter/tree-sitter-python",
                version="0.20.0",
                last_updated=datetime(2023, 1, 1),
                stars=500,
                description="Python grammar for tree-sitter",
                supported_extensions=[".py", ".pyw"],
                official=True,
            )
        elif language == "rust":
            return GrammarInfo(
                name="rust",
                url="https://github.com/tree-sitter/tree-sitter-rust",
                version="0.20.0",
                last_updated=datetime(2023, 1, 1),
                stars=400,
                description="Rust grammar for tree-sitter",
                supported_extensions=[".rs"],
                official=True,
            )
        return None

    def check_grammar_updates(
        self,
        installed_grammars: dict[str, str],
    ) -> dict[str, tuple[str, str]]:
        """Stub that simulates updates available"""
        updates = {}
        for lang, version in installed_grammars.items():
            if (
                lang == "python"
                and version < "0.20.0"
                or lang == "rust"
                and version < "0.20.0"
            ):
                updates[lang] = (version, "0.20.0")
        return updates

    def get_grammar_compatibility(
        self,
        language: str,
        version: str,
    ) -> GrammarCompatibility:
        """Stub that returns valid compatibility info"""
        return GrammarCompatibility(
            min_tree_sitter_version="0.20.0",
            max_tree_sitter_version="0.22.0",
            abi_version=14,
            tested_python_versions=["3.8", "3.9", "3.10", "3.11"],
        )

    def search_grammars(self, query: str) -> list[GrammarInfo]:
        """Stub that searches through minimal grammar list"""
        query_lower = query.lower()
        all_grammars = self.list_available_grammars(include_community=True)
        return [
            g
            for g in all_grammars
            if query_lower in g.name.lower() or query_lower in g.description.lower()
        ]

    def refresh_cache(self) -> bool:
        """Stub that always succeeds"""
        return True
