"""Tests for environment variable support in configuration."""

import json
import os
from pathlib import Path

from chunker.chunker_config import ChunkerConfig


class TestEnvironmentVariableExpansion:
    """Test environment variable expansion in config files."""

    @classmethod
    def test_expand_simple_env_var(cls):
        """Test expanding simple environment variables."""
        os.environ["TEST_VAR"] = "test_value"
        config = ChunkerConfig()
        result = config._expand_env_vars("${TEST_VAR}")
        assert result == "test_value"
        del os.environ["TEST_VAR"]

    @classmethod
    def test_expand_env_var_with_default(cls):
        """Test expanding environment variables with defaults."""
        config = ChunkerConfig()
        result = config._expand_env_vars("${NONEXISTENT_VAR:default_value}")
        assert result == "default_value"
        os.environ["EXISTING_VAR"] = "actual_value"
        result = config._expand_env_vars("${EXISTING_VAR:default_value}")
        assert result == "actual_value"
        del os.environ["EXISTING_VAR"]

    @classmethod
    def test_expand_env_vars_in_dict(cls):
        """Test expanding environment variables in dictionaries."""
        os.environ["DIR_PATH"] = "/custom/path"
        os.environ["LANG"] = "python"
        config = ChunkerConfig()
        data = {
            "plugin_dirs": [
                "${DIR_PATH}/plugins",
                "~/.chunker/plugins",
            ],
            "language": "${LANG}",
            "nested": {"value": "${DIR_PATH}/data"},
        }
        result = config._expand_env_vars(data)
        assert result["plugin_dirs"][0] == "/custom/path/plugins"
        assert result["language"] == "python"
        assert result["nested"]["value"] == "/custom/path/data"
        del os.environ["DIR_PATH"]
        del os.environ["LANG"]

    @classmethod
    def test_expand_env_vars_in_list(cls):
        """Test expanding environment variables in lists."""
        os.environ["PATH1"] = "/path/one"
        os.environ["PATH2"] = "/path/two"
        config = ChunkerConfig()
        data = ["${PATH1}", "${PATH2}", "static/path"]
        result = config._expand_env_vars(data)
        assert result == ["/path/one", "/path/two", "static/path"]
        del os.environ["PATH1"]
        del os.environ["PATH2"]

    @classmethod
    def test_env_var_in_config_file(cls, tmp_path):
        """Test loading config file with environment variables."""
        os.environ["CUSTOM_PLUGIN_DIR"] = "/custom/plugins"
        os.environ["MIN_SIZE"] = "5"
        config_data = {
            "chunker": {
                "plugin_dirs": ["${CUSTOM_PLUGIN_DIR}", "${HOME}/.chunker/plugins"],
                "default_plugin_config": {"min_chunk_size": "${MIN_SIZE:3}"},
            },
        }
        config_file = tmp_path / "config.json"
        with Path(config_file).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = ChunkerConfig(config_file)
        assert Path("/custom/plugins") in config.plugin_dirs
        del os.environ["CUSTOM_PLUGIN_DIR"]
        del os.environ["MIN_SIZE"]


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides for configuration."""

    @classmethod
    def test_override_enabled_languages(cls):
        """Test overriding enabled languages via environment variable."""
        os.environ["CHUNKER_ENABLED_LANGUAGES"] = "python,rust,javascript"
        config = ChunkerConfig()
        config._apply_env_overrides()
        assert config.enabled_languages == {"python", "rust", "javascript"}
        del os.environ["CHUNKER_ENABLED_LANGUAGES"]

    @classmethod
    def test_override_plugin_dirs(cls):
        """Test overriding plugin directories via environment variable."""
        os.environ["CHUNKER_PLUGIN_DIRS"] = "/path/one,/path/two,/path/three"
        config = ChunkerConfig()
        config._apply_env_overrides()
        assert len(config.plugin_dirs) == 3
        assert Path("/path/one") in config.plugin_dirs
        assert Path("/path/two") in config.plugin_dirs
        assert Path("/path/three") in config.plugin_dirs
        del os.environ["CHUNKER_PLUGIN_DIRS"]

    @classmethod
    def test_override_language_config(cls):
        """Test overriding language-specific configuration."""
        os.environ["CHUNKER_LANGUAGES_PYTHON_ENABLED"] = "false"
        os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"] = "10"
        os.environ["CHUNKER_LANGUAGES_PYTHON_MAX_CHUNK_SIZE"] = "1000"
        os.environ["CHUNKER_LANGUAGES_PYTHON_CHUNK_TYPES"] = (
            "function_definition,class_definition"
        )
        config = ChunkerConfig()
        config._apply_env_overrides()
        python_config = config.plugin_configs["python"]
        assert python_config.enabled is False
        assert python_config.min_chunk_size == 10
        assert python_config.max_chunk_size == 1000
        assert python_config.chunk_types == {"function_definition", "class_definition"}
        del os.environ["CHUNKER_LANGUAGES_PYTHON_ENABLED"]
        del os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"]
        del os.environ["CHUNKER_LANGUAGES_PYTHON_MAX_CHUNK_SIZE"]
        del os.environ["CHUNKER_LANGUAGES_PYTHON_CHUNK_TYPES"]

    @classmethod
    def test_override_custom_language_options(cls):
        """Test overriding custom language options."""
        os.environ["CHUNKER_LANGUAGES_PYTHON_INCLUDE_DOCSTRINGS"] = "true"
        os.environ["CHUNKER_LANGUAGES_JAVASCRIPT_INCLUDE_JSX"] = "false"
        config = ChunkerConfig()
        config._apply_env_overrides()
        assert (
            config.plugin_configs["python"].custom_options["include_docstrings"]
            == "true"
        )
        assert (
            config.plugin_configs["javascript"].custom_options["include_jsx"] == "false"
        )
        del os.environ["CHUNKER_LANGUAGES_PYTHON_INCLUDE_DOCSTRINGS"]
        del os.environ["CHUNKER_LANGUAGES_JAVASCRIPT_INCLUDE_JSX"]

    @classmethod
    def test_override_default_plugin_config(cls):
        """Test overriding default plugin configuration."""
        os.environ["CHUNKER_DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE"] = "20"
        os.environ["CHUNKER_DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE"] = "2000"
        config = ChunkerConfig()
        config._apply_env_overrides()
        assert config.default_plugin_config.min_chunk_size == 20
        assert config.default_plugin_config.max_chunk_size == 2000
        del os.environ["CHUNKER_DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE"]
        del os.environ["CHUNKER_DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE"]

    @classmethod
    def test_env_override_with_config_file(cls, tmp_path):
        """Test that environment variables override config file values."""
        config_data = {
            "chunker": {
                "enabled_languages": ["python", "rust"],
                "default_plugin_config": {"min_chunk_size": 3},
            },
            "languages": {"python": {"enabled": True, "min_chunk_size": 5}},
        }
        config_file = tmp_path / "config.json"
        with Path(config_file).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        os.environ["CHUNKER_ENABLED_LANGUAGES"] = "python,javascript,go"
        os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"] = "15"
        config = ChunkerConfig(config_file)
        assert config.enabled_languages == {"python", "javascript", "go"}
        assert config.plugin_configs["python"].min_chunk_size == 15
        del os.environ["CHUNKER_ENABLED_LANGUAGES"]
        del os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"]


class TestEnvironmentVariableInfo:
    """Test environment variable documentation."""

    @staticmethod
    def test_get_env_var_info():
        """Test getting environment variable information."""
        info = ChunkerConfig.get_env_var_info()
        assert "CHUNKER_ENABLED_LANGUAGES" in info
        assert "CHUNKER_PLUGIN_DIRS" in info
        assert "CHUNKER_LANGUAGES_<LANG>_ENABLED" in info
        assert "CHUNKER_LANGUAGES_<LANG>_MIN_CHUNK_SIZE" in info
        for desc in info.values():
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestIntegration:
    """Integration tests for environment variable support."""

    @classmethod
    def test_disable_env_vars(cls, tmp_path):
        """Test disabling environment variable support."""
        os.environ["CHUNKER_ENABLED_LANGUAGES"] = "should,not,be,used"
        config_data = {"chunker": {"enabled_languages": ["python", "rust"]}}
        config_file = tmp_path / "config.json"
        with Path(config_file).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = ChunkerConfig(config_file, use_env_vars=False)
        assert config.enabled_languages == {"python", "rust"}
        del os.environ["CHUNKER_ENABLED_LANGUAGES"]

    @classmethod
    def test_complex_scenario(cls, tmp_path):
        """Test complex scenario with multiple environment variables and config."""
        os.environ["BASE_DIR"] = "/base"
        os.environ["CHUNKER_ENABLED_LANGUAGES"] = "python,rust,go"
        os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"] = "8"
        os.environ["CHUNKER_LANGUAGES_RUST_ENABLED"] = "false"
        config_data = {
            "chunker": {
                "plugin_dirs": ["${BASE_DIR}/plugins", "~/.chunker/plugins"],
                "enabled_languages": ["python", "javascript"],
                "default_plugin_config": {"min_chunk_size": "${MIN_SIZE:5}"},
            },
            "languages": {"python": {"enabled": True, "min_chunk_size": 3}},
        }
        config_file = tmp_path / "config.json"
        with Path(config_file).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = ChunkerConfig(config_file)
        assert Path("/base/plugins") in config.plugin_dirs
        assert config.enabled_languages == {"python", "rust", "go"}
        assert config.plugin_configs["python"].min_chunk_size == 8
        assert config.plugin_configs["rust"].enabled is False
        del os.environ["BASE_DIR"]
        del os.environ["CHUNKER_ENABLED_LANGUAGES"]
        del os.environ["CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE"]
        del os.environ["CHUNKER_LANGUAGES_RUST_ENABLED"]
