"""Tests for the template generator implementation."""
import tempfile
from pathlib import Path

import pytest

from chunker.template_generator import TemplateGenerator


class TestTemplateGenerator:
    """Test suite for TemplateGenerator."""

    @classmethod
    @pytest.fixture
    def temp_dir(cls):
        """Create a temporary directory for test outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @classmethod
    @pytest.fixture
    def generator(cls):
        """Create a TemplateGenerator instance."""
        return TemplateGenerator()

    @staticmethod
    def test_generator_initialization(generator):
        """Test generator initializes correctly."""
        assert generator.template_dir.exists()
        assert (generator.template_dir / "language_plugin.py.j2").exists()
        assert (generator.template_dir / "language_test.py.j2").exists()

    @staticmethod
    def test_validate_language_name(generator):
        """Test language name validation."""
        assert generator._validate_language_name("css") is True
        assert generator._validate_language_name("html") is True
        assert generator._validate_language_name("python3") is True
        assert generator._validate_language_name("CSS") is False
        assert generator._validate_language_name("c++") is False
        assert generator._validate_language_name("my-lang") is False
        assert generator._validate_language_name("my lang") is False

    @staticmethod
    def test_validate_config(generator):
        """Test config validation."""
        config = {"node_types": ["function", "class"], "file_extensions": [
            ".css"]}
        assert generator._validate_config(config) is True
        config = {"file_extensions": [".css"]}
        assert generator._validate_config(config) is False
        config = {"node_types": ["function"]}
        assert generator._validate_config(config) is False

    @staticmethod
    def test_validate_test_cases(generator):
        """Test test case validation."""
        test_cases = [{"name": "test1", "code": "function() {}"}, {"name":
            "test2", "code": "class A {}"}]
        assert generator._validate_test_cases(test_cases) is True
        test_cases = [{"code": "test"}]
        assert generator._validate_test_cases(test_cases) is False
        test_cases = [{"name": "test"}]
        assert generator._validate_test_cases(test_cases) is False
        assert generator._validate_test_cases([]) is False

    @staticmethod
    def test_prepare_plugin_variables(generator):
        """Test plugin template variable preparation."""
        config = {"node_types": ["function", "class"], "file_extensions": [
            "css", ".scss"], "include_decorators": True,
            "custom_node_handling": {"function":
            "return node.children_count > 0"}}
        template_vars = generator._prepare_plugin_variables("css", config)
        assert template_vars["language_name"] == "css"
        assert template_vars["class_name"] == "Css"
        assert template_vars["node_types"] == ["function", "class"]
        assert ".css" in vars["file_extensions"]
        assert ".scss" in vars["file_extensions"]
        assert template_vars["include_decorators"] is True
        assert "function" in vars["custom_node_handling"]

    @staticmethod
    def test_prepare_test_variables(generator):
        """Test test template variable preparation."""
        test_cases = [{"name": "test_functions", "code":
            "function test() {}", "expected_chunks": 2, "expected_types": [
            "function"]}, {"name": "test_classes", "code": "class A {}"}]
        template_vars = generator._prepare_test_variables("css", test_cases)
        assert template_vars["language_name"] == "css"
        assert template_vars["class_name"] == "Css"
        assert len(vars["test_cases"]) == 2
        assert template_vars["test_cases"][0]["name"] == "test_functions"
        assert template_vars["test_cases"][0]["expected_chunks"] == 2
        assert template_vars["test_cases"][1]["expected_chunks"] == 1

    @staticmethod
    def test_generate_plugin_invalid_inputs(generator):
        """Test plugin generation with invalid inputs."""
        config = {"node_types": ["function"], "file_extensions": [".css"]}
        success, path = generator.generate_plugin("CSS", config)
        assert success is False
        success, _path = generator.generate_plugin("css", {})
        assert success is False

    @staticmethod
    def test_generate_test_invalid_inputs(generator):
        """Test test generation with invalid inputs."""
        test_cases = [{"name": "test", "code": "test"}]
        success, path = generator.generate_test("CSS", test_cases)
        assert success is False
        success, _path = generator.generate_test("css", [])
        assert success is False

    @staticmethod
    def test_validate_plugin_valid_file(generator, temp_dir):
        """Test validation of a valid plugin file."""
        plugin_path = temp_dir / "test_plugin.py"
        plugin_content = """""\"Test plugin.""\"
from tree_sitter import Node
from .plugin_base import LanguagePlugin
from ..contracts.language_plugin_contract import ExtendedLanguagePluginContract

class TestPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    def get_semantic_chunks(self, node, source):
        pass
    def get_chunk_node_types(self):
        pass
    def should_chunk_node(self, node):
        pass
    def get_node_context(self, node, source):
        pass
    @property
    def language_name(self):
        return "test"
    @property
    def supported_extensions(self):
        return {".test"}
    @property
    def default_chunk_types(self):
        return {"function"}
    def get_node_name(self, node, source):
        pass
"""
        plugin_path.write_text(plugin_content)
        is_valid, issues = generator.validate_plugin(plugin_path)
        assert is_valid is True
        assert len(issues) == 0

    @classmethod
    def test_validate_plugin_missing_file(cls, generator):
        """Test validation of non-existent file."""
        is_valid, issues = generator.validate_plugin(Path(
            "/nonexistent/plugin.py"))
        assert is_valid is False
        assert len(issues) == 1
        assert "does not exist" in issues[0]

    @staticmethod
    def test_validate_plugin_syntax_error(generator, temp_dir):
        """Test validation of file with syntax errors."""
        plugin_path = temp_dir / "bad_plugin.py"
        plugin_path.write_text("class BadPlugin(\n    # Syntax error")
        is_valid, issues = generator.validate_plugin(plugin_path)
        assert is_valid is False
        assert any("Syntax error" in issue for issue in issues)

    @staticmethod
    def test_validate_plugin_missing_imports(generator, temp_dir):
        """Test validation detects missing imports."""
        plugin_path = temp_dir / "incomplete_plugin.py"
        plugin_path.write_text("class TestPlugin:\n    pass\n")
        is_valid, issues = generator.validate_plugin(plugin_path)
        assert is_valid is False
        assert any("Missing required import" in issue for issue in issues)

    @staticmethod
    def test_validate_plugin_missing_methods(generator, temp_dir):
        """Test validation detects missing methods."""
        plugin_path = temp_dir / "incomplete_plugin.py"
        plugin_path.write_text(
            """from tree_sitter import Node
from .plugin_base import LanguagePlugin
from ..contracts.language_plugin_contract import ExtendedLanguagePluginContract

class TestPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    @property
    def language_name(self):
        return "test\"
""",
            )
        is_valid, issues = generator.validate_plugin(plugin_path)
        assert is_valid is False
        expected_missing = ["get_semantic_chunks", "get_chunk_node_types",
            "should_chunk_node", "get_node_context"]
        for method in expected_missing:
            assert any(method in issue for issue in issues)

    @classmethod
    def test_custom_template_dir(cls, temp_dir):
        """Test generator with custom template directory."""
        custom_template_dir = temp_dir / "custom_templates"
        custom_template_dir.mkdir()
        (custom_template_dir / "language_plugin.py.j2").write_text(
            "# Custom plugin for {{ language_name }}")
        (custom_template_dir / "language_test.py.j2").write_text(
            "# Custom test for {{ language_name }}")
        generator = TemplateGenerator(custom_template_dir)
        assert generator.template_dir == custom_template_dir

    @staticmethod
    def test_template_rendering(generator):
        """Test that templates can be rendered without errors."""
        template_vars = {"language_name": "test", "class_name": "Test",
            "node_types": ["function", "class"], "file_extensions": [
            ".test"], "include_imports": True, "include_decorators": False,
            "include_nested": True, "custom_node_handling": {}}
        template = generator._env.get_template("language_plugin.py.j2")
        content = template.render(**template_vars)
        assert "class TestPlugin" in content
        assert "language_name" in content
        assert "function" in content

    @staticmethod
    def test_integration_scenario(generator, temp_dir):
        """Test a full integration scenario."""
        config = {"node_types": ["style_rule", "media_rule",
            "keyframes_rule"], "file_extensions": [".css", ".scss"],
            "include_decorators": False}
        assert generator._validate_language_name("css") is True
        assert generator._validate_config(config) is True
        template_vars = generator._prepare_plugin_variables("css", config)
        assert template_vars["class_name"] == "Css"
        assert "style_rule" in vars["node_types"]
        template = generator._env.get_template("language_plugin.py.j2")
        content = template.render(**vars)
        assert "class CssPlugin" in content
