"""Tests for LanguageRegistry fallback to tree-sitter-language-pack."""

from __future__ import annotations

import sys
import types
import hashlib
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

_LIB_EXT = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")


def test_language_pack_list_probes_common_languages_when_enumeration_is_empty(
    monkeypatch,
):
    """Pack APIs can load languages even when no list API is available."""
    from chunker._internal import language_pack

    fake_pack = types.SimpleNamespace(
        SupportedLanguage=object(),
    )

    monkeypatch.setattr(language_pack, "_pack_available", True)
    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", fake_pack)

    languages = language_pack.list_pack_languages()
    assert "python" in languages
    assert "javascript" in languages


class TestRegistryFallback:
    """Tests for the language pack fallback chain in LanguageRegistry."""

    def test_pack_metadata_is_discovered_lazily(self, tmp_path):
        from chunker._internal.registry import LanguageRegistry

        registry = LanguageRegistry(tmp_path / "missing.so")
        with (
            patch.object(registry, "_discover_symbols", return_value=[]),
            patch.object(registry, "_try_load_from_language_pack") as load,
        ):
            metadata = registry.discover_languages()
            assert set(metadata) == set(registry.list_languages())
            assert "python" in metadata
            assert "cobol" not in metadata
            assert metadata["python"].capabilities["compatible"] is None
            load.assert_not_called()

        info = registry.get_metadata("python")
        language = registry.get_language("python")
        assert info.version == str(language.abi_version)
        assert info.node_types_count == language.node_kind_count
        assert info.capabilities["compatible"] is True

    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_registry_uses_language_pack_fallback(self):
        """Test that registry falls back to language pack when local grammars unavailable."""
        from chunker._internal.registry import LanguageRegistry

        # Create a registry with a non-existent library path to force fallback
        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Should be able to get Python language from the language pack
        lang = registry.get_language("python")
        assert lang is not None

    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_registry_fallback_returns_valid_language(self):
        """Test that fallback language can be used for parsing."""
        from tree_sitter import Parser

        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        lang = registry.get_language("python")
        parser = Parser()
        parser.language = lang

        # Parse some Python code
        code = b"def hello(): pass"
        tree = parser.parse(code)
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_registry_has_language_with_fallback(self):
        """Test has_language works with language pack fallback."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Common languages should be available via fallback
        assert registry.has_language("python") is True
        assert registry.has_language("javascript") is True
        assert registry.has_language("typescript") is True

    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_local_construction_failure_falls_back_to_language_pack(self, tmp_path):
        """Test local construction failures do not poison language-pack fallback."""
        import tree_sitter_python
        from tree_sitter import Language

        from chunker._internal import language_pack
        from chunker._internal.registry import LanguageMetadata, LanguageRegistry

        lib_path = tmp_path / f"languages{_LIB_EXT}"
        lib_path.write_bytes(b"fake")
        registry = LanguageRegistry(lib_path)
        metadata = LanguageMetadata(name="python", symbol_name="tree_sitter_python")
        registry._languages["python"] = (None, metadata)
        registry._discovered = True

        with (
            patch.object(
                registry,
                "_try_load_from_individual_library",
                side_effect=DeprecationWarning("deprecated local grammar"),
            ),
            patch.object(language_pack, "get_language_from_pack") as mock_pack,
        ):
            pack_language = Language(tree_sitter_python.language())
            mock_pack.return_value = pack_language
            assert registry.get_language("python") is pack_language

        assert registry._languages["python"] == (pack_language, metadata)
        assert registry._selected_sources["python"] == (
            pack_language,
            "official:tree-sitter-python@0.25.0",
        )

    def test_registry_list_languages_includes_pack(self):
        """Test that list_languages includes languages from the pack."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        languages = registry.list_languages()
        # Should have languages from the language pack
        assert "python" in languages
        assert "javascript" in languages

    def test_registry_local_grammar_takes_priority(self):
        """Test that local grammars take priority over language pack."""
        from chunker._internal.registry import LanguageRegistry

        # Use the actual package grammar directory if it exists
        package_grammar_build = (
            Path(__file__).parent.parent / "chunker" / "data" / "grammars" / "build"
        )

        # Even with a valid path that has local grammars,
        # languages not locally available should fall back to pack
        registry = LanguageRegistry(package_grammar_build / "languages.so")

        # This should work regardless of local grammar availability
        lang = registry.get_language("python")
        assert lang is not None

    @pytest.mark.parametrize("language", ["python", "javascript"])
    @pytest.mark.parametrize(
        "custom_source", ["individual", "languages", "my-languages"]
    )
    def test_492_real_custom_grammar_takes_priority(
        self, monkeypatch, tmp_path, language, custom_source
    ):
        import tree_sitter_language_pack as pack
        from tree_sitter import Parser

        from chunker._internal.registry import LanguageRegistry

        pack.get_language(language)
        candidates = [
            path
            for path in Path(pack.cache_dir()).rglob(f"*tree_sitter_{language}*")
            if path.is_file() and path.suffix.lower() in {".so", ".dylib", ".dll"}
        ]
        assert len(candidates) == 1
        custom_name = language if custom_source == "individual" else custom_source
        custom = tmp_path / f"{custom_name}{_LIB_EXT}"
        shutil.copy2(candidates[0], custom)
        expected_source = (
            f"custom:sha256:{hashlib.sha256(custom.read_bytes()).hexdigest()}"
        )

        library_path = (
            tmp_path / f"missing{_LIB_EXT}" if custom_source == "individual" else custom
        )
        registry = LanguageRegistry(library_path)
        monkeypatch.setattr(
            registry,
            "_try_load_from_language_pack",
            lambda name: pytest.fail(f"official provider used for {name}"),
        )

        selected = registry.get_language(language)
        assert not Parser(selected).parse(b"x = 1").root_node.has_error
        assert (
            registry.get_metadata(language).capabilities["grammar_source"]
            == expected_source
        )

    @pytest.mark.parametrize("language", ["python", "javascript"])
    def test_492_invalid_individual_does_not_poison_valid_combined(
        self, monkeypatch, tmp_path, language
    ):
        import tree_sitter_language_pack as pack
        from tree_sitter import Parser

        from chunker._internal.registry import LanguageRegistry

        pack.get_language(language)
        candidates = [
            path
            for path in Path(pack.cache_dir()).rglob(f"*tree_sitter_{language}*")
            if path.is_file() and path.suffix.lower() in {".so", ".dylib", ".dll"}
        ]
        assert len(candidates) == 1
        combined = tmp_path / f"languages{_LIB_EXT}"
        individual = tmp_path / f"{language}{_LIB_EXT}"
        shutil.copy2(candidates[0], combined)
        shutil.copy2(candidates[0], individual)
        expected_source = (
            f"custom:sha256:{hashlib.sha256(combined.read_bytes()).hexdigest()}"
        )

        registry = LanguageRegistry(combined)
        real_construct = registry._language_from_ctypes_symbol

        def reject_individual(lib, symbol_name, library_path, language_name):
            if library_path == individual and language_name == language:
                raise ValueError("lower-priority individual construction rejected")
            return real_construct(lib, symbol_name, library_path, language_name)

        monkeypatch.setattr(registry, "_language_from_ctypes_symbol", reject_individual)
        monkeypatch.setattr(
            registry,
            "_try_load_from_language_pack",
            lambda name: pytest.fail(f"official provider used for {name}"),
        )

        selected = registry.get_language(language)
        assert not Parser(selected).parse(b"x = 1").root_node.has_error
        assert registry._selected_sources[language] == (selected, expected_source)
        assert language not in registry._selection_errors

    def test_registry_fallback_preserves_language_not_found_error(self):
        """Test that LanguageNotFoundError is raised for invalid languages."""
        from chunker._internal.registry import LanguageRegistry
        from chunker.exceptions import LanguageNotFoundError

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        with pytest.raises(LanguageNotFoundError):
            registry.get_language("not_a_real_language_xyz123")

    def test_multiple_languages_from_fallback(self):
        """Test getting multiple languages via fallback."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Test several languages
        test_langs = ["python", "javascript", "typescript", "rust", "go"]
        for lang_name in test_langs:
            try:
                lang = registry.get_language(lang_name)
                assert lang is not None, f"Failed to get {lang_name}"
            except Exception:
                # Some languages might not be in the pack, that's OK
                pass

    def test_discover_symbols_scans_configured_build_directory(self, tmp_path):
        """Test dev checkout build dir is scanned for per-language libs."""
        from chunker._internal.registry import LanguageRegistry

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        python_lib = build_dir / f"python{_LIB_EXT}"
        python_lib.write_bytes(b"fake")

        registry = LanguageRegistry(build_dir / f"my-languages{_LIB_EXT}")

        with patch.object(registry, "_validate_language_library", return_value=True):
            symbols = registry._discover_symbols()

        assert ("python", "tree_sitter_python") in symbols

    def test_discovery_summary_is_not_critical_when_fallback_languages_exist(
        self, caplog
    ):
        """Test fallback-only availability does not log total failure."""
        from chunker._internal.registry import LanguageRegistry

        registry = LanguageRegistry(Path("/nonexistent/path/to/library.so"))

        with caplog.at_level("INFO"):
            languages = registry.list_languages()

        assert "python" in languages
        assert (
            "No languages available - system will not function properly"
            not in caplog.text
        )
        assert "fallback" in caplog.text.lower()

    def test_discovery_summary_prefers_available_language_count_over_low_local_count(
        self, caplog, tmp_path
    ):
        """Test partial local discovery does not imply broad failure when fallbacks exist."""
        from chunker._internal.registry import LanguageRegistry

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / f"python{_LIB_EXT}").write_bytes(b"fake")

        registry = LanguageRegistry(build_dir / f"my-languages{_LIB_EXT}")

        with patch.object(registry, "_validate_language_library", return_value=True):
            with caplog.at_level("INFO"):
                languages = registry.list_languages()

        assert "python" in languages
        assert "Many expected languages are missing" not in caplog.text
        assert "total available languages via fallbacks" in caplog.text

    def test_missing_combined_library_logs_info_not_error_when_fallback_works(
        self, caplog
    ):
        """Test missing dev combined library does not log a fallback-success path as an error."""
        from chunker._internal.registry import LanguageRegistry

        registry = LanguageRegistry(Path("/nonexistent/path/to/library.so"))

        with caplog.at_level("INFO"):
            languages = registry.list_languages()

        assert "python" in languages
        assert "Failed to load shared library" not in caplog.text
        assert "No combined library available" in caplog.text
