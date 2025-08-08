"""Unit tests for the GrammarManager implementation."""

import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chunker.grammar_manager import GrammarManager, GrammarManagerError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def grammar_manager(temp_dir):
    """Create a GrammarManager instance with temporary directories."""
    config_file = temp_dir / "config" / "grammar_sources.json"
    config_file.parent.mkdir(parents=True)
    test_sources = {
        "python": "https://github.com/tree-sitter/tree-sitter-python.git",
        "javascript": "https://github.com/tree-sitter/tree-sitter-javascript.git",
    }
    with config_file.open("w", "r") as f:
        json.dump(test_sources, f)
    return GrammarManager(root_dir=temp_dir, config_file=config_file, max_workers=2)


class TestGrammarManager:
    """Test suite for GrammarManager."""

    @staticmethod
    def test_initialization(grammar_manager, temp_dir):
        """Test that GrammarManager initializes correctly."""
        assert grammar_manager._root_dir == temp_dir
        assert grammar_manager._grammars_dir == temp_dir / "grammars"
        assert grammar_manager._build_dir == temp_dir / "build"
        assert grammar_manager._grammars_dir.exists()
        assert grammar_manager._build_dir.exists()
        assert len(grammar_manager._grammar_sources) == 2

    @staticmethod
    def test_add_grammar_source_success(grammar_manager):
        """Test successfully adding a new grammar source."""
        result = grammar_manager.add_grammar_source(
            "rust",
            "https://github.com/tree-sitter/tree-sitter-rust.git",
        )
        assert result is True
        assert "rust" in grammar_manager._grammar_sources
        with grammar_manager._config_file.open() as f:
            saved_config = json.load(f)
        assert "rust" in saved_config

    @staticmethod
    def test_add_grammar_source_duplicate(grammar_manager):
        """Test adding a duplicate grammar source."""
        result = grammar_manager.add_grammar_source(
            "python",
            "https://github.com/other/tree-sitter-python.git",
        )
        assert result is False
        assert (
            grammar_manager._grammar_sources["python"]
            == "https://github.com/tree-sitter/tree-sitter-python.git"
        )

    @staticmethod
    def test_add_grammar_source_invalid_url(grammar_manager):
        """Test adding grammar with invalid URL."""
        with pytest.raises(GrammarManagerError, match="Invalid GitHub URL"):
            grammar_manager.add_grammar_source("test", "not-a-url")
        with pytest.raises(GrammarManagerError, match="Invalid GitHub URL"):
            grammar_manager.add_grammar_source("test", "https://example.com/repo.git")

    @classmethod
    @patch("subprocess.run")
    def test_fetch_grammars_success(cls, mock_run, grammar_manager):
        """Test successfully fetching grammars."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Cloning into...",
            stderr="",
        )
        results = grammar_manager.fetch_grammars()
        assert len(results) == 2
        assert results["python"] is True
        assert results["javascript"] is True
        assert mock_run.call_count == 2

    @classmethod
    @patch("subprocess.run")
    def test_fetch_grammars_partial_failure(cls, mock_run, grammar_manager):
        """Test fetching with some failures."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Success", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Failed to clone", check=False),
        ]
        mock_run.side_effect[1].side_effect = Exception("Clone failed")
        results = grammar_manager.fetch_grammars()
        assert len(results) == 2
        assert any(v for v in results.values())

    @staticmethod
    def test_fetch_grammars_specific_languages(grammar_manager):
        """Test fetching specific languages only."""
        python_dir = grammar_manager._grammars_dir / "tree-sitter-python"
        python_dir.mkdir(parents=True)
        results = grammar_manager.fetch_grammars(["python", "javascript"])
        assert results["python"] is True
        assert len(results) == 2

    @staticmethod
    def test_fetch_grammars_unknown_language(grammar_manager):
        """Test fetching with unknown language."""
        results = grammar_manager.fetch_grammars(["unknown", "python"])
        assert "unknown" not in results
        assert "python" in results

    @classmethod
    @patch("subprocess.run")
    def test_compile_grammars_success(cls, mock_run, grammar_manager):
        """Test successfully compiling grammars."""
        for lang in ["python", "javascript"]:
            lang_dir = grammar_manager._grammars_dir / f"tree-sitter-{lang}"
            src_dir = lang_dir / "src"
            src_dir.mkdir(parents=True)
            c_file = src_dir / "parser.c"
            c_file.write_text("/* dummy parser */")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Compilation successful",
            stderr="",
        )
        results = grammar_manager.compile_grammars()
        assert len(results) == 2
        assert results["python"] is True
        assert results["javascript"] is True
        assert mock_run.call_count == 1
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "gcc"
        assert "-shared" in call_args
        assert "-fPIC" in call_args

    @staticmethod
    def test_compile_grammars_no_sources(grammar_manager):
        """Test compiling when no C sources exist."""
        lang_dir = grammar_manager._grammars_dir / "tree-sitter-python"
        lang_dir.mkdir(parents=True)
        results = grammar_manager.compile_grammars(["python"])
        assert results["python"] is False

    @classmethod
    @patch("subprocess.run")
    def test_compile_grammars_failure(cls, mock_run, grammar_manager):
        """Test compilation failure."""
        lang_dir = grammar_manager._grammars_dir / "tree-sitter-python"
        src_dir = lang_dir / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "parser.c").write_text("/* dummy */")
        mock_run.side_effect = Exception("Compilation error")
        results = grammar_manager.compile_grammars(["python"])
        assert results["python"] is False

    @staticmethod
    def test_get_available_languages_no_library(grammar_manager):
        """Test getting languages when library doesn't exist."""
        languages = grammar_manager.get_available_languages()
        assert languages == set()

    @classmethod
    @patch("ctypes.CDLL")
    def test_get_available_languages_with_library(cls, mock_cdll, grammar_manager):
        """Test getting languages from compiled library."""
        grammar_manager._lib_path.touch()
        mock_lib = MagicMock()
        mock_cdll.return_value = mock_lib

        def mock_getattr(name):
            if name in {"tree_sitter_python", "tree_sitter_javascript"}:
                return MagicMock()
            raise AttributeError(f"Symbol {name} not found")

        mock_lib.__getattr__ = mock_getattr
        languages = grammar_manager.get_available_languages()
        assert "python" in languages
        assert "javascript" in languages

    @classmethod
    def test_get_available_languages_fallback(cls, grammar_manager):
        """Test fallback language detection from directories."""
        grammar_manager._lib_path.touch()
        for lang in ["python", "rust"]:
            (grammar_manager._grammars_dir / f"tree-sitter-{lang}").mkdir(parents=True)
        with patch("ctypes.CDLL", side_effect=Exception("Load failed")):
            languages = grammar_manager.get_available_languages()
        assert "python" in languages
        assert "rust" in languages

    @staticmethod
    def test_concurrent_operations(grammar_manager):
        """Test thread safety of concurrent operations."""
        results = []
        errors = []

        def add_language(lang, url):
            try:
                result = grammar_manager.add_grammar_source(lang, url)
                results.append((lang, result))
            except (OSError, ImportError, IndexError) as e:
                errors.append((lang, str(e)))

        threads = []
        for i in range(5):
            lang = f"lang{i}"
            url = f"https://github.com/test/tree-sitter-{lang}.git"
            t = threading.Thread(target=add_language, args=(lang, url))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(results) == 5
        for i in range(5):
            assert f"lang{i}" in grammar_manager._grammar_sources

    @classmethod
    def test_empty_config_handling(cls, temp_dir):
        """Test handling of missing config file."""
        manager = GrammarManager(
            root_dir=temp_dir,
            config_file=temp_dir / "nonexistent" / "config.json",
        )
        assert len(manager._grammar_sources) == 0
        result = manager.add_grammar_source(
            "test",
            "https://github.com/test/tree-sitter-test.git",
        )
        assert result is True
        assert manager._config_file.exists()
