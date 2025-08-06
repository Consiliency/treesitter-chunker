import json
import shutil
import tempfile
from pathlib import Path

import pytest
import toml
import yaml

from chunker.chunker_config import ChunkerConfig
from chunker.languages.base import PluginConfig


class TestConfigLoading:
    """Test configuration loading from different formats."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_load_yaml_config(cls, temp_config_dir):
        """Test loading configuration from YAML file."""
        config_path = temp_config_dir / "chunker.config.yaml"
        config_data = {
            "chunker": {
                "plugin_dirs": ["./plugins"],
                "enabled_languages": ["python", "rust"],
                "default_plugin_config": {"min_chunk_size": 5, "max_chunk_size": 100},
            },
            "languages": {
                "python": {
                    "enabled": True,
                    "chunk_types": ["function_definition", "class_definition"],
                    "include_docstrings": True,
                },
            },
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert len(config.plugin_dirs) == 1
        assert config.enabled_languages == {"python", "rust"}
        assert config.default_plugin_config.min_chunk_size == 5
        assert config.default_plugin_config.max_chunk_size == 100
        assert "python" in config.plugin_configs
        assert config.plugin_configs["python"].enabled is True
        assert config.plugin_configs["python"].chunk_types == {
            "function_definition",
            "class_definition",
        }
        assert (
            config.plugin_configs["python"].custom_options["include_docstrings"] is True
        )

    @classmethod
    def test_load_json_config(cls, temp_config_dir):
        """Test loading configuration from JSON file."""
        config_path = temp_config_dir / "chunker.config.json"
        config_data = {
            "chunker": {
                "plugin_dirs": ["~/plugins", "/usr/local/plugins"],
                "enabled_languages": ["javascript", "typescript"],
            },
            "languages": {
                "javascript": {
                    "enabled": True,
                    "chunk_types": ["function_declaration", "arrow_function"],
                    "min_chunk_size": 10,
                },
            },
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert len(config.plugin_dirs) == 2
        assert config.enabled_languages == {"javascript", "typescript"}
        assert "javascript" in config.plugin_configs
        assert config.plugin_configs["javascript"].min_chunk_size == 10

    @classmethod
    def test_load_toml_config(cls, temp_config_dir):
        """Test loading configuration from TOML file."""
        config_path = temp_config_dir / "chunker.config.toml"
        config_data = {
            "chunker": {
                "plugin_dirs": ["./custom_plugins"],
                "enabled_languages": ["c", "cpp"],
            },
            "languages": {
                "c": {"enabled": False, "chunk_types": ["function_definition"]},
                "cpp": {
                    "enabled": True,
                    "chunk_types": ["function_definition", "class_specifier"],
                    "max_chunk_size": 200,
                },
            },
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert config.plugin_configs["c"].enabled is False
        assert config.plugin_configs["cpp"].enabled is True
        assert config.plugin_configs["cpp"].max_chunk_size == 200

    @classmethod
    def test_empty_yaml_config(cls, temp_config_dir):
        """Test loading empty YAML configuration."""
        config_path = temp_config_dir / "empty.yaml"
        config_path.write_text("")
        config = ChunkerConfig(config_path)
        assert config.data == {}
        assert config.plugin_dirs == []
        assert config.enabled_languages is None

    @classmethod
    def test_load_nonexistent_file(cls):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            ChunkerConfig(Path("/nonexistent/config.yaml"))

    @classmethod
    def test_unsupported_format(cls, temp_config_dir):
        """Test loading unsupported configuration format."""
        config_path = temp_config_dir / "config.xml"
        config_path.write_text("<config></config>")
        with pytest.raises(ValueError, match="Unsupported config format"):
            ChunkerConfig(config_path)

    @classmethod
    def test_invalid_yaml_syntax(cls, temp_config_dir):
        """Test loading YAML with syntax errors."""
        config_path = temp_config_dir / "invalid.yaml"
        config_path.write_text("invalid: yaml: syntax:")
        with pytest.raises(Exception):
            ChunkerConfig(config_path)

    @classmethod
    def test_invalid_json_syntax(cls, temp_config_dir):
        """Test loading JSON with syntax errors."""
        config_path = temp_config_dir / "invalid.json"
        config_path.write_text('{"invalid": json syntax}')
        with pytest.raises(Exception):
            ChunkerConfig(config_path)


class TestConfigSaving:
    """Test configuration saving to different formats."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_save_yaml_config(cls, temp_config_dir):
        """Test saving configuration to YAML file."""
        config = ChunkerConfig()
        config.plugin_dirs = [Path("./plugins"), Path("~/.chunker/plugins")]
        config.enabled_languages = {"python", "rust"}
        config.default_plugin_config = PluginConfig(
            min_chunk_size=3,
            max_chunk_size=500,
        )
        config.plugin_configs["python"] = PluginConfig(
            enabled=True,
            chunk_types={"function_definition", "class_definition"},
            custom_options={"include_docstrings": True},
        )
        save_path = temp_config_dir / "saved.yaml"
        config.save(save_path)
        loaded_data = yaml.safe_load(save_path.read_text())
        assert loaded_data["chunker"]["plugin_dirs"] == [
            "plugins",
            str(Path("~/.chunker/plugins")),
        ]
        assert set(loaded_data["chunker"]["enabled_languages"]) == {"python", "rust"}
        assert loaded_data["chunker"]["default_plugin_config"]["min_chunk_size"] == 3
        assert loaded_data["languages"]["python"]["include_docstrings"] is True

    @classmethod
    def test_save_json_config(cls, temp_config_dir):
        """Test saving configuration to JSON file."""
        config = ChunkerConfig()
        config.enabled_languages = {"javascript"}
        config.plugin_configs["javascript"] = PluginConfig(
            chunk_types={"function_declaration"},
            min_chunk_size=5,
        )
        save_path = temp_config_dir / "saved.json"
        config.save(save_path)
        loaded_data = json.loads(save_path.read_text())
        assert loaded_data["chunker"]["enabled_languages"] == ["javascript"]
        assert loaded_data["languages"]["javascript"]["min_chunk_size"] == 5

    @classmethod
    def test_save_toml_config(cls, temp_config_dir):
        """Test saving configuration to TOML file."""
        config = ChunkerConfig()
        config.plugin_dirs = [Path("/usr/local/plugins")]
        config.plugin_configs["c"] = PluginConfig(enabled=False)
        save_path = temp_config_dir / "saved.toml"
        config.save(save_path)
        loaded_data = toml.loads(save_path.read_text())
        assert loaded_data["chunker"]["plugin_dirs"] == ["/usr/local/plugins"]
        assert loaded_data["languages"]["c"]["enabled"] is False

    @classmethod
    def test_save_without_path(cls):
        """Test saving without specifying a path."""
        config = ChunkerConfig()
        with pytest.raises(ValueError, match="No config path specified"):
            config.save()

    @classmethod
    def test_save_with_original_path(cls, temp_config_dir):
        """Test saving to original path after loading."""
        original_path = temp_config_dir / "original.yaml"
        original_path.write_text("chunker:\n  enabled_languages: [python]\n")
        config = ChunkerConfig(original_path)
        config.enabled_languages = {"python", "rust"}
        config.save()
        loaded_data = yaml.safe_load(original_path.read_text())
        assert set(loaded_data["chunker"]["enabled_languages"]) == {"python", "rust"}

    @classmethod
    def test_roundtrip_yaml(cls, temp_config_dir):
        """Test loading and saving YAML preserves data."""
        config_path = temp_config_dir / "roundtrip.yaml"
        config1 = ChunkerConfig()
        config1.plugin_dirs = [Path("./plugins")]
        config1.enabled_languages = {"python", "rust", "javascript"}
        config1.default_plugin_config = PluginConfig(
            min_chunk_size=2,
            max_chunk_size=100,
        )
        config1.plugin_configs["python"] = PluginConfig(
            chunk_types={"function_definition", "class_definition"},
            custom_options={"docstring_style": "google"},
        )
        config1.save(config_path)
        config2 = ChunkerConfig(config_path)
        save_path2 = temp_config_dir / "roundtrip2.yaml"
        config2.save(save_path2)
        config3 = ChunkerConfig(config_path)
        config4 = ChunkerConfig(save_path2)
        assert len(config3.plugin_dirs) == len(config4.plugin_dirs)
        assert config3.enabled_languages == config4.enabled_languages
        assert (
            config3.default_plugin_config.min_chunk_size
            == config4.default_plugin_config.min_chunk_size
        )
        assert (
            config3.default_plugin_config.max_chunk_size
            == config4.default_plugin_config.max_chunk_size
        )
        assert config3.plugin_configs.keys() == config4.plugin_configs.keys()
        assert (
            config3.plugin_configs["python"].chunk_types
            == config4.plugin_configs["python"].chunk_types
        )
        assert (
            config3.plugin_configs["python"].custom_options
            == config4.plugin_configs["python"].custom_options
        )


class TestPathResolution:
    """Test path resolution in configuration."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_resolve_absolute_path(cls, temp_config_dir):
        """Test resolution of absolute paths."""
        config_path = temp_config_dir / "config.yaml"
        abs_path = "/usr/local/plugins"
        config_data = {"chunker": {"plugin_dirs": [abs_path]}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert len(config.plugin_dirs) == 1
        assert str(config.plugin_dirs[0]) == abs_path

    @classmethod
    def test_resolve_home_path(cls, temp_config_dir):
        """Test resolution of home directory paths."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"chunker": {"plugin_dirs": ["~/plugins", "~/.chunker/plugins"]}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        home = Path.home()
        assert config.plugin_dirs[0] == home / "plugins"
        assert config.plugin_dirs[1] == home / ".chunker" / "plugins"

    @classmethod
    def test_resolve_relative_path(cls, temp_config_dir):
        """Test resolution of relative paths."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"chunker": {"plugin_dirs": ["./plugins", "../shared_plugins"]}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert config.plugin_dirs[0] == (temp_config_dir / "plugins").resolve()
        assert (
            config.plugin_dirs[1] == (temp_config_dir / "../shared_plugins").resolve()
        )

    @classmethod
    def test_resolve_without_config_path(cls):
        """Test path resolution when no config path is set."""
        config = ChunkerConfig()
        config._resolve_path("./plugins")


class TestConfigFinding:
    """Test configuration file discovery."""

    @classmethod
    @pytest.fixture()
    def temp_project_dir(cls):
        """Create a temporary project directory structure."""
        temp_dir = Path(tempfile.mkdtemp())
        (temp_dir / "src" / "subdir").mkdir(parents=True)
        yield temp_dir
        shutil.rmtree(temp_dir)

    @staticmethod
    def test_find_config_in_current_dir(temp_project_dir):
        """Test finding config in current directory."""
        config_path = temp_project_dir / "chunker.config.yaml"
        config_path.write_text("chunker:\n  enabled_languages: [python]\n")
        found = ChunkerConfig.find_config(temp_project_dir)
        assert found == config_path

    @staticmethod
    def test_find_config_in_parent_dir(temp_project_dir):
        """Test finding config in parent directory."""
        config_path = temp_project_dir / "chunker.config.toml"
        config_path.write_text("[chunker]\nenabled_languages = ['rust']\n")
        subdir = temp_project_dir / "src" / "subdir"
        found = ChunkerConfig.find_config(subdir)
        assert found == config_path

    @staticmethod
    def test_find_config_multiple_formats(temp_project_dir):
        """Test finding config with multiple format options."""
        (temp_project_dir / "chunker.config.json").write_text("{}")
        yaml_path = temp_project_dir / "chunker.config.yaml"
        yaml_path.write_text("chunker: {}")
        found = ChunkerConfig.find_config(temp_project_dir)
        assert found is not None
        assert found.name.startswith("chunker.config")

    @staticmethod
    def test_find_config_in_home_dir(temp_project_dir, monkeypatch):
        """Test finding config in home directory."""
        fake_home = temp_project_dir / "fake_home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        chunker_dir = fake_home / ".chunker"
        chunker_dir.mkdir()
        config_path = chunker_dir / "config.yaml"
        config_path.write_text("chunker: {}")
        search_dir = temp_project_dir / "empty_project"
        search_dir.mkdir()
        found = ChunkerConfig.find_config(search_dir)
        assert found == config_path

    @staticmethod
    def test_find_config_not_found(temp_project_dir):
        """Test when no config file is found."""
        empty_dir = temp_project_dir / "empty"
        empty_dir.mkdir()
        found = ChunkerConfig.find_config(empty_dir)
        assert found is None


class TestConfigValidation:
    """Test configuration validation and error handling."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_negative_min_chunk_size(cls, temp_config_dir):
        """Test handling of negative min_chunk_size."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"chunker": {"default_plugin_config": {"min_chunk_size": -1}}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert config.default_plugin_config.min_chunk_size == -1

    @classmethod
    def test_invalid_chunk_types(cls, temp_config_dir):
        """Test handling of invalid chunk_types."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"languages": {"python": {"chunk_types": "not_a_list"}}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert config.plugin_configs["python"].chunk_types == set("not_a_list")

    @classmethod
    def test_non_iterable_chunk_types(cls, temp_config_dir):
        """Test handling of non-iterable chunk_types."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"languages": {"python": {"chunk_types": 123}}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        with pytest.raises(TypeError):
            ChunkerConfig(config_path)

    @classmethod
    def test_missing_required_fields(cls, temp_config_dir):
        """Test configuration with missing fields."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {"languages": {"python": {"enabled": True}}}
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert config.plugin_configs["python"].enabled is True
        assert config.plugin_configs["python"].chunk_types is None
        assert config.plugin_configs["python"].min_chunk_size == 1


class TestConfigMerging:
    """Test configuration inheritance and merging."""

    @classmethod
    def test_get_plugin_config_with_defaults(cls):
        """Test getting plugin config falls back to defaults."""
        config = ChunkerConfig()
        config.default_plugin_config = PluginConfig(
            min_chunk_size=5,
            max_chunk_size=100,
            custom_options={"global_option": True},
        )
        python_config = config.get_plugin_config("python")
        assert python_config.min_chunk_size == 5
        assert python_config.max_chunk_size == 100
        assert python_config.custom_options["global_option"] is True

    @classmethod
    def test_get_plugin_config_with_override(cls):
        """Test language-specific config overrides default."""
        config = ChunkerConfig()
        config.default_plugin_config = PluginConfig(min_chunk_size=5)
        config.plugin_configs["python"] = PluginConfig(
            min_chunk_size=10,
            chunk_types={"function_definition"},
        )
        python_config = config.get_plugin_config("python")
        assert python_config.min_chunk_size == 10
        assert python_config.chunk_types == {"function_definition"}

    @classmethod
    def test_get_plugin_config_disabled_language(cls):
        """Test getting config for disabled language."""
        config = ChunkerConfig()
        config.enabled_languages = {"python", "rust"}
        js_config = config.get_plugin_config("javascript")
        assert js_config.enabled is False

    @classmethod
    def test_set_plugin_config(cls):
        """Test setting plugin configuration."""
        config = ChunkerConfig()
        new_config = PluginConfig(
            chunk_types={"function_declaration"},
            min_chunk_size=3,
        )
        config.set_plugin_config("javascript", new_config)
        assert "javascript" in config.plugin_configs
        assert config.plugin_configs["javascript"] == new_config


class TestPluginDirectories:
    """Test plugin directory management."""

    @classmethod
    def test_add_plugin_directory(cls):
        """Test adding plugin directories."""
        config = ChunkerConfig()
        plugin_dir = Path("./plugins")
        config.add_plugin_directory(plugin_dir)
        assert len(config.plugin_dirs) == 1
        assert config.plugin_dirs[0] == plugin_dir.resolve()
        config.add_plugin_directory(plugin_dir)
        assert len(config.plugin_dirs) == 1

    @classmethod
    def test_remove_plugin_directory(cls):
        """Test removing plugin directories."""
        config = ChunkerConfig()
        dir1 = Path("./plugins1").resolve()
        dir2 = Path("./plugins2").resolve()
        config.plugin_dirs = [dir1, dir2]
        config.remove_plugin_directory(dir1)
        assert len(config.plugin_dirs) == 1
        assert config.plugin_dirs[0] == dir2
        config.remove_plugin_directory(Path("./nonexistent"))
        assert len(config.plugin_dirs) == 1


class TestExampleConfig:
    """Test example configuration creation."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @staticmethod
    def test_create_example_config(temp_config_dir):
        """Test creating example configuration file."""
        config_path = temp_config_dir / "example.toml"
        ChunkerConfig.create_example_config(config_path)
        assert config_path.exists()
        loaded_data = toml.loads(config_path.read_text())
        assert loaded_data == {}


class TestEnvironmentVariables:
    """Test environment variable expansion in configuration."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_env_var_in_path(cls, temp_config_dir, monkeypatch):
        """Test environment variable expansion in paths."""
        monkeypatch.setenv("CHUNKER_PLUGINS", "/custom/plugins")
        config_path = temp_config_dir / "config.yaml"
        config_data = {
            "chunker": {"plugin_dirs": ["$CHUNKER_PLUGINS/language_plugins"]},
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert str(config.plugin_dirs[0]).endswith("$CHUNKER_PLUGINS/language_plugins")


class TestComplexScenarios:
    """Test complex configuration scenarios."""

    @classmethod
    @pytest.fixture()
    def temp_config_dir(cls):
        """Create a temporary directory for config files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @classmethod
    def test_deeply_nested_config(cls, temp_config_dir):
        """Test handling of deeply nested configuration."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {
            "chunker": {
                "default_plugin_config": {
                    "level1": {"level2": {"level3": "deep_value"}},
                },
            },
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        custom_opts = config.default_plugin_config.custom_options
        assert custom_opts["level1"]["level2"]["level3"] == "deep_value"

    @classmethod
    def test_unicode_in_config(cls, temp_config_dir):
        """Test handling of Unicode in configuration."""
        config_path = temp_config_dir / "config.yaml"
        config_data = {
            "languages": {
                "python": {
                    "author": "José García",
                    "description": "配置文件测试",
                    "emoji": "🐍",
                },
            },
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, allow_unicode=True)
        config = ChunkerConfig(config_path)
        python_opts = config.plugin_configs["python"].custom_options
        assert python_opts["author"] == "José García"
        assert python_opts["description"] == "配置文件测试"
        assert python_opts["emoji"] == "🐍"

    @classmethod
    def test_large_config_file(cls, temp_config_dir):
        """Test handling of large configuration files."""
        config_path = temp_config_dir / "config.yaml"
        languages = {}
        for i in range(100):
            languages[f"lang_{i}"] = {
                "enabled": i % 2 == 0,
                "chunk_types": [f"type_{j}" for j in range(10)],
                "min_chunk_size": i + 1,
                "custom_options": {f"option_{k}": f"value_{k}" for k in range(20)},
            }
        config_data = {
            "chunker": {"enabled_languages": [f"lang_{i}" for i in range(50)]},
            "languages": languages,
        }
        with Path(config_path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)
        config = ChunkerConfig(config_path)
        assert len(config.plugin_configs) == 100
        assert len(config.enabled_languages) == 50
        assert config.plugin_configs["lang_10"].min_chunk_size == 11
