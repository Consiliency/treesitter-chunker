"""Unit tests for grammar repository."""

from pathlib import Path

from chunker.grammar.repository import (
    KNOWN_GRAMMARS,
    POPULAR_LANGUAGES,
    TreeSitterGrammarRepository,
    get_grammar_repository,
)
from chunker.interfaces.grammar import GrammarStatus


class TestTreeSitterGrammarRepository:
    """Test the TreeSitterGrammarRepository class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo = TreeSitterGrammarRepository()

    def test_search_by_name(self):
        """Test searching grammars by name."""
        # Search for python
        results = self.repo.search("python")
        assert len(results) == 1
        assert results[0].name == "python"
        assert results[0].repository_url == KNOWN_GRAMMARS["python"]["url"]

        # Search for 'script' should find JavaScript and TypeScript
        results = self.repo.search("script")
        assert len(results) >= 2
        names = [r.name for r in results]
        assert "javascript" in names
        assert "typescript" in names

    def test_search_by_description(self):
        """Test searching grammars by description."""
        # Search for 'programming'
        results = self.repo.search("programming")
        assert len(results) > 0

        # All results should have 'programming' in description
        for result in results:
            grammar_info = KNOWN_GRAMMARS.get(result.name, {})
            assert "programming" in grammar_info.get("description", "").lower()

    def test_get_popular_grammars(self):
        """Test getting popular grammars."""
        # Get default
        popular = self.repo.get_popular_grammars()
        assert len(popular) <= 20
        assert len(popular) <= len(POPULAR_LANGUAGES)

        # Check all are from popular list
        for grammar in popular:
            assert grammar.name in POPULAR_LANGUAGES

        # Get limited
        popular_5 = self.repo.get_popular_grammars(limit=5)
        assert len(popular_5) == 5

    def test_get_grammar_by_extension(self):
        """Test finding grammar by file extension."""
        # Test common extensions
        test_cases = [
            (".py", "python"),
            (".js", "javascript"),
            (".rs", "rust"),
            (".go", "go"),
            (".rb", "ruby"),
            (".java", "java"),
            (".cpp", "cpp"),
            (".c", "c"),
            (".cs", "csharp"),
            (".php", "php"),
            (".swift", "swift"),
            (".kt", "kotlin"),
        ]

        for ext, expected_lang in test_cases:
            grammar = self.repo.get_grammar_by_extension(ext)
            assert grammar is not None, f"No grammar found for {ext}"
            assert grammar.name == expected_lang

        # Test without dot
        grammar = self.repo.get_grammar_by_extension("py")
        assert grammar is not None
        assert grammar.name == "python"

        # Test unknown extension
        grammar = self.repo.get_grammar_by_extension(".xyz")
        assert grammar is None

    def test_get_grammar_info(self):
        """Test getting specific grammar info."""
        # Get known grammar
        info = self.repo.get_grammar_info("go")
        assert info is not None
        assert info.name == "go"
        assert info.repository_url == KNOWN_GRAMMARS["go"]["url"]
        assert info.status == GrammarStatus.NOT_FOUND

        # Get unknown grammar
        info = self.repo.get_grammar_info("unknown")
        assert info is None

    def test_list_all_grammars(self):
        """Test listing all grammar names."""
        all_names = self.repo.list_all_grammars()

        # Should be sorted
        assert all_names == sorted(all_names)

        # Should contain known languages
        for lang in ["python", "javascript", "rust", "go", "ruby", "java"]:
            assert lang in all_names

        # Should match KNOWN_GRAMMARS
        assert len(all_names) == len(KNOWN_GRAMMARS)

    def test_refresh_repository(self):
        """Test refreshing repository data."""
        # For now, just test it doesn't crash
        result = self.repo.refresh_repository()
        assert result is True

    def test_custom_repository_file(self):
        """Test loading custom repositories."""
        import json
        import tempfile

        # Create custom repo file
        custom_grammars = {
            "mylang": {
                "url": "https://github.com/example/tree-sitter-mylang",
                "extensions": [".ml", ".myl"],
                "description": "My custom language",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom_grammars, f)
            custom_file = Path(f.name)

        try:
            # Create repo with custom file
            repo = TreeSitterGrammarRepository(custom_repo_file=custom_file)

            # Check custom grammar is available
            info = repo.get_grammar_info("mylang")
            assert info is not None
            assert info.name == "mylang"

            # Check extension mapping
            grammar = repo.get_grammar_by_extension(".ml")
            assert grammar is not None
            assert grammar.name == "mylang"

            # Original grammars should still be there
            assert repo.get_grammar_info("python") is not None

        finally:
            custom_file.unlink()

    def test_singleton_instance(self):
        """Test that get_grammar_repository returns singleton."""
        repo1 = get_grammar_repository()
        repo2 = get_grammar_repository()
        assert repo1 is repo2
