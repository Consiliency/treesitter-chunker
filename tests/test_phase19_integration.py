from pathlib import Path

from chunker.contracts.grammar_manager_stub import GrammarManagerStub
from chunker.contracts.language_plugin_stub import ExtendedLanguagePluginStub
from chunker.contracts.template_generator_stub import TemplateGeneratorStub


def test_template_generator_integration():
    """Test that template generator produces valid plugin files"""
    # Arrange: Create real stub instances
    generator = TemplateGeneratorStub()

    # Act: Generate a plugin
    config = {
        "node_types": ["rule_set", "media_statement"],
        "file_extensions": [".css", ".scss"],
    }
    success, plugin_path = generator.generate_plugin("css", config)

    # Assert: Verify return types match contract
    assert isinstance(success, bool), f"Expected bool, got {type(success)}"
    assert isinstance(plugin_path, Path), f"Expected Path, got {type(plugin_path)}"
    assert plugin_path.name == "css.py"


def test_grammar_compilation_integration():
    """Test grammar manager integration with build system"""

    # Arrange
    manager = GrammarManagerStub()

    # Act: Add and compile grammars
    success = manager.add_grammar_source(
        "css",
        "https://github.com/tree-sitter/tree-sitter-css",
    )
    languages = manager.get_available_languages()

    # Assert: Verify types
    assert isinstance(success, bool)
    assert isinstance(languages, set)


def test_multi_language_plugin_loading():
    """Test that multiple language plugins can coexist"""

    # Arrange: Multiple language stubs
    css_plugin = ExtendedLanguagePluginStub()
    html_plugin = ExtendedLanguagePluginStub()
    json_plugin = ExtendedLanguagePluginStub()

    # Act: Get chunk types from each
    css_types = css_plugin.get_chunk_node_types()
    html_types = html_plugin.get_chunk_node_types()
    json_types = json_plugin.get_chunk_node_types()

    # Assert: All return correct types
    assert isinstance(css_types, set)
    assert isinstance(html_types, set)
    assert isinstance(json_types, set)
    assert len(css_types) > 0  # Must be non-empty per contract


def test_plugin_parser_integration():
    """Test that plugins integrate with parser factory"""

    # Arrange
    plugin = ExtendedLanguagePluginStub()

    # Act: Simulate parsing
    chunks = plugin.get_semantic_chunks(None, b"test code")  # type: ignore[arg-type]

    # Assert: Returns correct structure
    assert isinstance(chunks, list)
    # Would check chunk structure if non-empty


def test_template_validation_integration():
    """Test that template validation works correctly"""

    # Arrange
    generator = TemplateGeneratorStub()

    # Act: Validate a plugin
    valid, issues = generator.validate_plugin(Path("test_plugin.py"))

    # Assert: Correct return types
    assert isinstance(valid, bool)
    assert isinstance(issues, list)
    if issues:
        assert all(isinstance(issue, str) for issue in issues)


def test_grammar_fetch_integration():
    """Test grammar fetching returns expected structure"""

    # Arrange
    manager = GrammarManagerStub()

    # Act
    fetch_results = manager.fetch_grammars(["css", "html", "json"])
    compile_results = manager.compile_grammars(["css", "html", "json"])

    # Assert
    assert isinstance(fetch_results, dict)
    assert isinstance(compile_results, dict)
    # Real implementation would have language keys with bool values


def test_plugin_context_extraction():
    """Test that plugins can extract context correctly"""

    # Arrange
    plugin = ExtendedLanguagePluginStub()

    # Act
    context = plugin.get_node_context(None, b"test code")  # type: ignore[arg-type]
    should_chunk = plugin.should_chunk_node(None)  # type: ignore[arg-type]

    # Assert
    assert context is None or isinstance(context, str)
    assert isinstance(should_chunk, bool)
