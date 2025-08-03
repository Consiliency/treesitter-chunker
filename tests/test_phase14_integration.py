"""Test Phase 14 Universal Language Support Integration.

Components involved: Discovery, Download, Registry, Zero-Config
Expected behavior: Seamless grammar discovery, download, and usage
"""
import tempfile

import pytest

from chunker.contracts.auto_stub import ZeroConfigStub
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_stub import GrammarDownloadStub
from chunker.contracts.registry_stub import UniversalRegistryStub


class TestDiscoveryDownloadIntegration:
    """Test integration between grammar discovery and download services"""

    @classmethod
    def test_discover_and_download_grammar(cls):
        """Test discovering a grammar and downloading it"""
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()
        grammars = discovery.list_available_grammars()
        first_grammar = grammars[0]
        success, path = downloader.download_and_compile(first_grammar.name,
            first_grammar.version)
        assert isinstance(grammars, list,
            ), f"Expected list, got {type(grammars)}"
        assert len(grammars) > 0, "Should have at least one grammar"
        assert hasattr(first_grammar, "name",
            ), "Grammar should have name attribute"
        assert hasattr(first_grammar, "version"), "Grammar should have version"
        assert isinstance(success, bool), f"Expected bool, got {type(success)}"
        assert isinstance(path, str), f"Expected str, got {type(path)}"
        assert success is True, "Download should succeed"

    @classmethod
    def test_grammar_compatibility_check(cls):
        """Test checking grammar compatibility before download"""
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()
        compat = discovery.get_grammar_compatibility("python", "0.20.0")
        download_path = downloader.download_grammar("python", "0.20.0")
        compiled_result = downloader.compile_grammar(download_path,
            download_path.parent)
        assert compat.abi_version == compiled_result.abi_version
        assert isinstance(compat.min_tree_sitter_version, str)
        assert isinstance(compat.tested_python_versions, list)


class TestRegistryAutoIntegration:
    """Test integration between registry and zero-config API"""

    @classmethod
    def test_auto_download_through_registry(cls):
        """Test automatic grammar download when using registry"""
        registry = UniversalRegistryStub()
        auto_api = ZeroConfigStub()
        initial_installed = registry.list_installed_languages()
        go_ready = auto_api.ensure_language("go")
        parser = registry.get_parser("go", auto_download=True)
        assert "go" not in initial_installed, "Go should not be initially installed"
        assert go_ready is True, "ensure_language should succeed"
        assert parser is not None, "Parser should be returned"
        assert registry.is_language_installed("go",
            ), "Go should now be installed"

    @classmethod
    def test_file_chunking_with_auto_download(cls):
        """Test chunking a file that requires grammar download"""
        auto_api = ZeroConfigStub()
        UniversalRegistryStub()
        with tempfile.NamedTemporaryFile(encoding="utf-8", suffix=".go",
            mode="w") as f:
            f.write("package main\n\nfunc main() {}")
            f.flush()
            result = auto_api.auto_chunk_file(f.name)
            assert hasattr(result, "chunks"), "Result should have chunks"
            assert hasattr(result, "language"), "Result should have language"
            assert hasattr(result, "grammar_downloaded",
                ), "Result should have download flag"
            assert result.language == "go", f"Should detect Go, got {result.language}"
            assert isinstance(result.chunks, list), "Chunks should be a list"
            assert len(result.chunks) > 0, "Should have at least one chunk"
            chunk = result.chunks[0]
            assert "content" in chunk, "Chunk should have content"
            assert "type" in chunk, "Chunk should have type"


class TestFullWorkflowIntegration:
    """Test complete workflow from discovery to chunking"""

    @classmethod
    def test_discover_download_register_chunk(cls):
        """Test full workflow for a new language"""
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()
        registry = UniversalRegistryStub()
        auto_api = ZeroConfigStub()
        java_grammars = discovery.search_grammars("java")
        assert len(java_grammars) == 0, "Java not in minimal stub list"
        all_available = discovery.list_available_grammars()
        python_info = next((g for g in all_available if g.name == "python"),
            None)
        assert python_info is not None
        if not downloader.is_grammar_cached("python"):
            success, _path = downloader.download_and_compile("python")
            assert success is True
        assert registry.is_language_installed("python")
        result = auto_api.chunk_text("def hello(): pass", "python")
        assert len(result.chunks) > 0
        assert result.language == "python"

    @classmethod
    def test_preload_multiple_languages(cls):
        """Test preloading multiple languages for offline use"""
        auto_api = ZeroConfigStub()
        registry = UniversalRegistryStub()
        languages_to_preload = ["go", "java", "ruby"]
        results = auto_api.preload_languages(languages_to_preload)
        assert isinstance(results, dict)
        for lang in languages_to_preload:
            assert lang in results
            assert results[lang] is True, f"Failed to preload {lang}"
        for lang in languages_to_preload:
            if results[lang]:
                registry.install_language(lang)
        for lang in languages_to_preload:
            metadata = registry.get_language_metadata(lang)
            assert metadata != {}, f"No metadata for {lang}"
            assert "version" in metadata


class TestErrorHandlingIntegration:
    """Test error handling across components"""

    @classmethod
    def test_invalid_language_handling(cls):
        """Test handling of invalid language requests"""
        auto_api = ZeroConfigStub()
        registry = UniversalRegistryStub()
        result = auto_api.ensure_language("not-a-real-language")
        assert result is False, "Should fail for invalid language"
        with pytest.raises(ValueError):
            registry.get_parser("not-a-real-language", auto_download=False)

    @classmethod
    def test_cache_management(cls):
        """Test cache cleanup integration"""
        downloader = GrammarDownloadStub()
        registry = UniversalRegistryStub()
        for lang in ["python", "rust", "go"]:
            registry.install_language(lang)
        removed = downloader.clean_cache(keep_recent=2)
        assert isinstance(removed, int)
        assert removed >= 0, "Should remove non-negative number"
