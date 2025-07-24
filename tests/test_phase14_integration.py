"""Test Phase 14 Universal Language Support Integration.

Components involved: Discovery, Download, Registry, Zero-Config
Expected behavior: Seamless grammar discovery, download, and usage
"""

import tempfile

import pytest

from chunker.contracts.auto_stub import ZeroConfigStub

# CRITICAL: Import stub implementations, not Mock!
from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_stub import GrammarDownloadStub
from chunker.contracts.registry_stub import UniversalRegistryStub


class TestDiscoveryDownloadIntegration:
    """Test integration between grammar discovery and download services"""

    def test_discover_and_download_grammar(self):
        """Test discovering a grammar and downloading it"""
        # Arrange: Create real stub instances (NOT Mock()!)
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()

        # Act: Discover available grammars
        grammars = discovery.list_available_grammars()

        # Download the first grammar
        first_grammar = grammars[0]
        success, path = downloader.download_and_compile(
            first_grammar.name,
            first_grammar.version,
        )

        # Assert: Verify return types and structure
        assert isinstance(grammars, list), f"Expected list, got {type(grammars)}"
        assert len(grammars) > 0, "Should have at least one grammar"
        assert hasattr(first_grammar, "name"), "Grammar should have name attribute"
        assert hasattr(first_grammar, "version"), "Grammar should have version"

        assert isinstance(success, bool), f"Expected bool, got {type(success)}"
        assert isinstance(path, str), f"Expected str, got {type(path)}"
        assert success is True, "Download should succeed"

    def test_grammar_compatibility_check(self):
        """Test checking grammar compatibility before download"""
        # Arrange
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()

        # Act: Get compatibility info
        compat = discovery.get_grammar_compatibility("python", "0.20.0")

        # Download and validate
        download_path = downloader.download_grammar("python", "0.20.0")
        compiled_result = downloader.compile_grammar(
            download_path,
            download_path.parent,
        )

        # Assert: Verify compatibility matches
        assert compat.abi_version == compiled_result.abi_version
        assert isinstance(compat.min_tree_sitter_version, str)
        assert isinstance(compat.tested_python_versions, list)


class TestRegistryAutoIntegration:
    """Test integration between registry and zero-config API"""

    def test_auto_download_through_registry(self):
        """Test automatic grammar download when using registry"""
        # Arrange
        registry = UniversalRegistryStub()
        auto_api = ZeroConfigStub()

        # Act: Request parser for non-installed language
        initial_installed = registry.list_installed_languages()

        # Use auto API to ensure language
        go_ready = auto_api.ensure_language("go")

        # Now try to get parser from registry
        parser = registry.get_parser("go", auto_download=True)

        # Assert: Verify language was made available
        assert "go" not in initial_installed, "Go should not be initially installed"
        assert go_ready is True, "ensure_language should succeed"
        assert parser is not None, "Parser should be returned"
        assert registry.is_language_installed("go"), "Go should now be installed"

    def test_file_chunking_with_auto_download(self):
        """Test chunking a file that requires grammar download"""
        # Arrange
        auto_api = ZeroConfigStub()
        registry = UniversalRegistryStub()

        with tempfile.NamedTemporaryFile(suffix=".go", mode="w") as f:
            f.write("package main\n\nfunc main() {}")
            f.flush()

            # Act: Auto chunk the Go file
            result = auto_api.auto_chunk_file(f.name)

            # Assert: Verify result structure
            assert hasattr(result, "chunks"), "Result should have chunks"
            assert hasattr(result, "language"), "Result should have language"
            assert hasattr(
                result,
                "grammar_downloaded",
            ), "Result should have download flag"

            assert result.language == "go", f"Should detect Go, got {result.language}"
            assert isinstance(result.chunks, list), "Chunks should be a list"
            assert len(result.chunks) > 0, "Should have at least one chunk"

            # Verify chunk structure
            chunk = result.chunks[0]
            assert "content" in chunk, "Chunk should have content"
            assert "type" in chunk, "Chunk should have type"


class TestFullWorkflowIntegration:
    """Test complete workflow from discovery to chunking"""

    def test_discover_download_register_chunk(self):
        """Test full workflow for a new language"""
        # Arrange: All components
        discovery = GrammarDiscoveryStub()
        downloader = GrammarDownloadStub()
        registry = UniversalRegistryStub()
        auto_api = ZeroConfigStub()

        # Act: Complete workflow
        # 1. Search for a language
        java_grammars = discovery.search_grammars("java")
        assert len(java_grammars) == 0, "Java not in minimal stub list"

        # 2. List all available
        all_available = discovery.list_available_grammars()
        python_info = next((g for g in all_available if g.name == "python"), None)
        assert python_info is not None

        # 3. Download if needed
        if not downloader.is_grammar_cached("python"):
            success, path = downloader.download_and_compile("python")
            assert success is True

        # 4. Register the grammar
        assert registry.is_language_installed("python")

        # 5. Use it to chunk
        result = auto_api.chunk_text("def hello(): pass", "python")
        assert len(result.chunks) > 0
        assert result.language == "python"

    def test_preload_multiple_languages(self):
        """Test preloading multiple languages for offline use"""
        # Arrange
        auto_api = ZeroConfigStub()
        registry = UniversalRegistryStub()

        # Act: Preload several languages
        languages_to_preload = ["go", "java", "ruby"]
        results = auto_api.preload_languages(languages_to_preload)

        # Assert: Verify all succeeded
        assert isinstance(results, dict)
        for lang in languages_to_preload:
            assert lang in results
            assert results[lang] is True, f"Failed to preload {lang}"

        # In a real integration, preloading would install in registry
        # Simulate this by installing in registry
        for lang in languages_to_preload:
            if results[lang]:
                registry.install_language(lang)

        # Verify they're ready in registry
        for lang in languages_to_preload:
            metadata = registry.get_language_metadata(lang)
            assert metadata != {}, f"No metadata for {lang}"
            assert "version" in metadata


class TestErrorHandlingIntegration:
    """Test error handling across components"""

    def test_invalid_language_handling(self):
        """Test handling of invalid language requests"""
        # Arrange
        auto_api = ZeroConfigStub()
        registry = UniversalRegistryStub()

        # Act & Assert: Invalid language
        result = auto_api.ensure_language("not-a-real-language")
        assert result is False, "Should fail for invalid language"

        # Registry should raise error without auto-download
        with pytest.raises(ValueError):
            registry.get_parser("not-a-real-language", auto_download=False)

    def test_cache_management(self):
        """Test cache cleanup integration"""
        # Arrange
        downloader = GrammarDownloadStub()
        registry = UniversalRegistryStub()

        # Act: Install several languages
        for lang in ["python", "rust", "go"]:
            registry.install_language(lang)

        # Clean cache
        removed = downloader.clean_cache(keep_recent=2)

        # Assert: Some grammars removed
        assert isinstance(removed, int)
        assert removed >= 0, "Should remove non-negative number"
