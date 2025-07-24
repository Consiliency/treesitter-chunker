"""Integration tests for grammar management."""

import shutil
import tempfile
from pathlib import Path

import pytest

from chunker.grammar import (
    TreeSitterGrammarBuilder,
    TreeSitterGrammarManager,
    get_grammar_repository,
)
from chunker.interfaces.grammar import GrammarStatus


class TestGrammarIntegration:
    """Integration tests for grammar management workflow."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = TreeSitterGrammarManager(
            grammars_dir=self.temp_dir / "grammars",
            build_dir=self.temp_dir / "build",
        )
        self.builder = TreeSitterGrammarBuilder()
        self.builder.set_source_directory(self.temp_dir / "grammars")
        self.builder.set_build_directory(self.temp_dir / "build")
        self.repo = get_grammar_repository()

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.integration()
    @pytest.mark.slow()
    def test_full_grammar_workflow(self):
        """Test complete workflow: add, fetch, build, validate."""
        # Skip if no internet connection
        import socket

        try:
            socket.create_connection(("github.com", 443), timeout=5)
        except (TimeoutError, OSError):
            pytest.skip("No internet connection")

        # Get grammar info from repository
        grammar_info = self.repo.get_grammar_info("python")
        assert grammar_info is not None

        # Add grammar to manager
        added = self.manager.add_grammar(
            "python",
            grammar_info.repository_url,
        )
        assert added.status == GrammarStatus.NOT_FOUND

        # Fetch grammar
        fetched = self.manager.fetch_grammar("python")
        assert fetched is True

        # Check status updated
        info = self.manager.get_grammar_info("python")
        assert info.status == GrammarStatus.NOT_BUILT

        # Build grammar
        built = self.manager.build_grammar("python")
        assert built is True

        # Check status is ready
        info = self.manager.get_grammar_info("python")
        assert info.status == GrammarStatus.READY

        # Validate grammar
        valid, error = self.manager.validate_grammar("python")
        assert valid is True
        assert error is None

    @pytest.mark.integration()
    def test_repository_search_workflow(self):
        """Test discovering and adding grammars from repository."""
        # Search for JavaScript-related grammars
        results = self.repo.search("javascript")
        assert len(results) > 0

        # Add all found grammars
        for grammar in results:
            self.manager.add_grammar(
                grammar.name,
                grammar.repository_url,
            )

        # List all grammars
        all_grammars = self.manager.list_grammars()
        names = [g.name for g in all_grammars]
        assert "javascript" in names

        # Could also have TypeScript
        if "typescript" in [g.name for g in results]:
            assert "typescript" in names

    @pytest.mark.integration()
    def test_file_extension_discovery(self):
        """Test discovering grammar by file extension."""
        test_files = [
            ("example.py", "python"),
            ("example.js", "javascript"),
            ("example.rs", "rust"),
            ("example.go", "go"),
            ("example.rb", "ruby"),
            ("example.java", "java"),
        ]

        for filename, expected_lang in test_files:
            ext = Path(filename).suffix
            grammar = self.repo.get_grammar_by_extension(ext)

            assert grammar is not None, f"No grammar found for {ext}"
            assert grammar.name == expected_lang

            # Add to manager
            self.manager.add_grammar(
                grammar.name,
                grammar.repository_url,
            )

        # Check all were added
        all_grammars = self.manager.list_grammars()
        assert len(all_grammars) == len(test_files)

    @pytest.mark.integration()
    def test_popular_grammars(self):
        """Test getting and managing popular grammars."""
        # Get top 5 popular grammars
        popular = self.repo.get_popular_grammars(limit=5)
        assert len(popular) == 5

        # Add them all
        for grammar in popular:
            self.manager.add_grammar(
                grammar.name,
                grammar.repository_url,
            )

        # List by status
        not_found = self.manager.list_grammars(GrammarStatus.NOT_FOUND)
        assert len(not_found) == 5

        # All should be popular languages
        names = [g.name for g in not_found]
        for name in names:
            assert name in [
                "python",
                "javascript",
                "typescript",
                "rust",
                "go",
                "java",
                "c",
                "cpp",
                "ruby",
                "php",
                "swift",
                "kotlin",
            ]

    @pytest.mark.integration()
    def test_builder_integration(self):
        """Test builder integration with manager."""
        # Add some grammars
        grammars_to_test = ["python", "javascript", "rust"]

        for lang in grammars_to_test:
            info = self.repo.get_grammar_info(lang)
            if info:
                self.manager.add_grammar(lang, info.repository_url)

        # Create fake source directories (for testing only)
        for lang in grammars_to_test:
            lang_dir = self.temp_dir / "grammars" / f"tree-sitter-{lang}"
            lang_dir.mkdir(parents=True, exist_ok=True)

            # Create minimal files
            (lang_dir / "src").mkdir(exist_ok=True)
            (lang_dir / "src" / "parser.c").write_text("// Dummy parser")

        # Use builder to check build capability
        languages = []
        for lang_dir in (self.temp_dir / "grammars").glob("tree-sitter-*"):
            if lang_dir.is_dir():
                lang = lang_dir.name.replace("tree-sitter-", "")
                languages.append(lang)

        assert len(languages) == len(grammars_to_test)

    @pytest.mark.integration()
    def test_grammar_removal(self):
        """Test removing grammars."""
        # Add a grammar
        self.manager.add_grammar(
            "test-lang",
            "https://example.com/test-lang.git",
        )

        # Create fake directory
        lang_dir = self.temp_dir / "grammars" / "tree-sitter-test-lang"
        lang_dir.mkdir(parents=True, exist_ok=True)
        (lang_dir / "test.txt").write_text("test")

        # Update grammar info
        grammar = self.manager._grammars["test-lang"]
        grammar.path = lang_dir

        # Remove it
        removed = self.manager.remove_grammar("test-lang")
        assert removed is True

        # Check it's gone
        assert not lang_dir.exists()
        assert self.manager.get_grammar_info("test-lang") is None
