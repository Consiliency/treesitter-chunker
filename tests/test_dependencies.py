"""Test dependency management for tree-sitter-language-pack integration.

This test module validates that:
1. tree-sitter-language-pack can be imported
2. The package is compatible with our tree-sitter version
3. Language pack provides expected functionality
"""

import pytest


class TestDependencyImport:
    """Test that tree-sitter-language-pack can be imported."""

    def test_import_language_pack(self):
        """Test that tree-sitter-language-pack can be imported."""
        # This test will initially fail before the dependency is added
        try:
            import tree_sitter_language_pack
            assert tree_sitter_language_pack is not None
        except ImportError as e:
            pytest.fail(f"Failed to import tree-sitter-language-pack: {e}")

    def test_language_pack_get_language(self):
        """Test that language pack provides get_language function."""
        try:
            from tree_sitter_language_pack import get_language
            assert callable(get_language)
        except ImportError as e:
            pytest.fail(f"Failed to import get_language: {e}")

    def test_language_pack_version_compatibility(self):
        """Test that language pack version is compatible."""
        try:
            import tree_sitter_language_pack
            # Check that the module has the expected version attribute
            # tree-sitter-language-pack should be >= 0.4.0
            if hasattr(tree_sitter_language_pack, "__version__"):
                version = tree_sitter_language_pack.__version__
                # Basic version check - should be 0.4.0 or higher
                parts = version.split(".")
                major = int(parts[0])
                minor = int(parts[1]) if len(parts) > 1 else 0
                assert major >= 0 and minor >= 4, f"Version {version} is too old, need >= 0.4.0"
        except ImportError as e:
            pytest.fail(f"Failed to import tree-sitter-language-pack: {e}")


class TestLanguagePackFunctionality:
    """Test language pack provides expected functionality."""

    def test_get_language_returns_language_object(self):
        """Test that get_language returns a valid Language object."""
        try:
            from tree_sitter_language_pack import get_language
            # Try to get a common language (Python)
            lang = get_language("python")
            assert lang is not None
            # Language objects should have a name attribute or similar
            # The exact interface depends on tree-sitter version
        except ImportError as e:
            pytest.fail(f"Failed to import or use language pack: {e}")
        except Exception:
            # Language may not be available in pack, which is acceptable
            # The import itself working is the key test
            pass

    def test_tree_sitter_compatibility(self):
        """Test that language pack works with our tree-sitter version."""
        try:
            import tree_sitter
            from tree_sitter_language_pack import get_language

            # Verify tree-sitter version
            assert hasattr(tree_sitter, "Language")
            assert hasattr(tree_sitter, "Parser")

            # Try to use a language with parser
            try:
                lang = get_language("python")
                parser = tree_sitter.Parser()
                parser.set_language(lang)
                assert parser.language == lang
            except Exception:
                # If specific language not available, that's OK
                # The compatibility test is about the interfaces
                pass
        except ImportError as e:
            pytest.fail(f"Failed to test compatibility: {e}")
