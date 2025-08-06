"""Unit tests for the ZeroConfigAPI implementation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chunker.auto import ZeroConfigAPI
from chunker.contracts.auto_contract import AutoChunkResult
from chunker.exceptions import ChunkerError
from chunker.types import CodeChunk


class MockRegistry:
    """Mock implementation of UniversalRegistryContract for testing."""

    def __init__(self):
        self.installed_languages = {"python", "javascript", "go"}
        self.available_languages = [
            "python",
            "javascript",
            "go",
            "java",
            "rust",
            "ruby",
        ]
        self.language_versions = {
            "python": "0.20.0",
            "javascript": "0.20.0",
            "go": "0.20.0",
        }
        self.parsers = {}

    def is_language_installed(self, language: str) -> bool:
        return language in self.installed_languages

    def list_installed_languages(self) -> list[str]:
        return sorted(self.installed_languages)

    def list_available_languages(self) -> list[str]:
        return sorted(self.available_languages)

    def install_language(
        self,
        language: str,
        version: str | None = None,
    ) -> bool:
        if language in self.available_languages:
            self.installed_languages.add(language)
            self.language_versions[language] = version or "0.20.0"
            return True
        return False

    def get_language_version(self, language: str) -> str | None:
        return self.language_versions.get(language)

    def update_language(self, language: str) -> tuple[bool, str]:
        if language in self.installed_languages:
            return True, f"Updated {language} to latest version"
        return False, f"Language {language} not installed"

    def get_parser(self, language: str, auto_download: bool = True):
        if language in self.installed_languages:
            return MagicMock()
        if auto_download and language in self.available_languages:
            self.install_language(language)
            return MagicMock()
        return None

    def uninstall_language(self, language: str) -> bool:
        if language in self.installed_languages:
            self.installed_languages.remove(language)
            del self.language_versions[language]
            return True
        return False

    def get_language_metadata(self, language: str) -> dict:
        if language in self.installed_languages:
            return {
                "version": self.language_versions[language],
                "extensions": [f".{language[:2]}"],
            }
        return {}


class TestZeroConfigAPI:
    """Test cases for ZeroConfigAPI."""

    @classmethod
    @pytest.fixture()
    def api(cls):
        """Create a ZeroConfigAPI instance with mock registry."""
        registry = MockRegistry()
        return ZeroConfigAPI(registry)

    @staticmethod
    def test_ensure_language_already_installed(api):
        """Test ensuring a language that's already installed."""
        assert api.ensure_language("python") is True
        assert api.registry.is_language_installed("python") is True

    @staticmethod
    def test_ensure_language_not_installed_but_available(api):
        """Test ensuring a language that needs to be installed."""
        assert api.registry.is_language_installed("rust") is False
        assert api.ensure_language("rust") is True
        assert api.registry.is_language_installed("rust") is True

    @staticmethod
    def test_ensure_language_not_available(api):
        """Test ensuring a language that's not available."""
        assert api.ensure_language("not-a-language") is False

    @staticmethod
    def test_ensure_language_with_version(api):
        """Test ensuring a specific version of a language."""
        assert api.ensure_language("python", "0.20.0") is True
        with patch.object(
            api.registry,
            "update_language",
            return_value=(True, "Updated"),
        ):
            assert api.ensure_language("python", "0.21.0") is True

    @classmethod
    def test_detect_language_by_extension(cls, api):
        """Test language detection by file extension."""
        assert api.detect_language(Path("test.py")) == "python"
        assert api.detect_language(Path("test.js")) == "javascript"
        assert api.detect_language(Path("test.rs")) == "rust"
        assert api.detect_language(Path("test.go")) == "go"
        assert api.detect_language(Path("test.unknown")) is None

    @classmethod
    def test_detect_language_by_shebang(cls, api):
        """Test language detection by shebang."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", delete=False) as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("print('hello')")
            f.flush()
            assert api.detect_language(Path(f.name)) == "python"
            Path(f.name).unlink()

    @classmethod
    def test_detect_language_special_files(cls, api):
        """Test language detection for special file names."""
        assert api.detect_language(Path("Makefile")) == "makefile"
        assert api.detect_language(Path("Dockerfile")) == "dockerfile"
        assert api.detect_language(Path("package.json")) == "json"
        assert api.detect_language(Path("Cargo.toml")) == "toml"

    @staticmethod
    def test_list_supported_extensions(api):
        """Test listing supported file extensions."""
        extensions = api.list_supported_extensions()
        assert isinstance(extensions, dict)
        assert "python" in extensions
        assert ".py" in extensions["python"]
        assert "javascript" in extensions
        assert ".js" in extensions["javascript"]

    @classmethod
    def test_auto_chunk_file_with_tree_sitter(cls, api):
        """Test auto chunking a file with tree-sitter available."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".py",
            mode="w",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')")
            f.flush()
            mock_chunks = [
                CodeChunk(
                    language="python",
                    file_path=f.name,
                    node_type="function_definition",
                    start_line=1,
                    end_line=2,
                    byte_start=0,
                    byte_end=30,
                    parent_context="",
                    content="""def hello():
    print('world')""",
                    metadata={"name": "hello"},
                ),
            ]
            with patch("chunker.auto.chunk_file", return_value=mock_chunks):
                result = api.auto_chunk_file(f.name)
            assert isinstance(result, AutoChunkResult)
            assert result.language == "python"
            assert result.fallback_used is False
            assert len(result.chunks) == 1
            assert result.chunks[0]["type"] == "function_definition"
            Path(f.name).unlink()

    @classmethod
    def test_auto_chunk_file_fallback(cls, api):
        """Test auto chunking falls back when tree-sitter fails."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".txt",
            mode="w",
            delete=False,
        ) as f:
            f.write("This is some text content\nthat should be chunked")
            f.flush()
            result = api.auto_chunk_file(f.name)
            assert isinstance(result, AutoChunkResult)
            assert result.language == "unknown"
            assert result.fallback_used is True
            assert len(result.chunks) > 0
            Path(f.name).unlink()

    @classmethod
    def test_auto_chunk_file_with_language_override(cls, api):
        """Test auto chunking with explicit language."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            suffix=".txt",
            mode="w",
            delete=False,
        ) as f:
            f.write("def hello():\n    print('world')")
            f.flush()
            mock_chunks = [
                CodeChunk(
                    language="python",
                    file_path=f.name,
                    node_type="function_definition",
                    start_line=1,
                    end_line=2,
                    byte_start=0,
                    byte_end=30,
                    parent_context="",
                    content="""def hello():
    print('world')""",
                ),
            ]
            with patch("chunker.auto.chunk_file", return_value=mock_chunks):
                result = api.auto_chunk_file(f.name, language="python")
            assert result.language == "python"
            assert result.fallback_used is False
            Path(f.name).unlink()

    @classmethod
    def test_chunk_text_success(cls, api):
        """Test chunking text content successfully."""
        text = "def hello():\n    print('world')"
        mock_chunks = [
            CodeChunk(
                language="python",
                file_path="",
                node_type="function_definition",
                start_line=1,
                end_line=2,
                byte_start=0,
                byte_end=len(text.encode()),
                parent_context="",
                content=text,
            ),
        ]
        with patch("chunker.auto.chunk_text", return_value=mock_chunks):
            result = api.chunk_text(text, "python")
        assert isinstance(result, AutoChunkResult)
        assert result.language == "python"
        assert result.fallback_used is False
        assert len(result.chunks) == 1

    @staticmethod
    def test_chunk_text_empty(api):
        """Test chunking empty text raises error."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            api.chunk_text("", "python")

    @staticmethod
    def test_chunk_text_no_language(api):
        """Test chunking text without language raises error."""
        with pytest.raises(ValueError, match="Language must be specified"):
            api.chunk_text("some text", "")

    @staticmethod
    def test_get_chunker_for_language(api):
        """Test getting a chunker for a specific language."""
        chunker = api.get_chunker_for_language("python", auto_download=False)
        assert hasattr(chunker, "chunk_file")
        assert hasattr(chunker, "chunk_text")
        chunker = api.get_chunker_for_language("rust", auto_download=True)
        assert api.registry.is_language_installed("rust")
        with pytest.raises(ChunkerError):
            api.get_chunker_for_language("not-a-language", auto_download=True)

    @staticmethod
    def test_preload_languages(api):
        """Test preloading multiple languages."""
        languages = ["rust", "java", "not-a-language"]
        results = api.preload_languages(languages)
        assert results["rust"] is True
        assert results["java"] is True
        assert results["not-a-language"] is False
        assert api.registry.is_language_installed("rust")
        assert api.registry.is_language_installed("java")
