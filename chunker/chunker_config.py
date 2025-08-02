from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import toml
import yaml

from .languages.base import PluginConfig

logger = logging.getLogger(__name__)


class ChunkerConfig:
    """Configuration manager for the chunker system.

    Supports environment variable expansion and overrides:
    - ${VAR} or ${VAR:default} syntax in config files
    - CHUNKER_* environment variables override config values
    """

    DEFAULT_CONFIG_FILENAME = "chunker.config"
    SUPPORTED_FORMATS = {".toml", ".yaml", ".yml", ".json"}
    ENV_PREFIX = "CHUNKER_"
    ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, config_path: Path | None = None, use_env_vars: bool = True):
        self.config_path = config_path
        self.data: dict[str, Any] = {}
        self.plugin_configs: dict[str, PluginConfig] = {}
        self.use_env_vars = use_env_vars

        # Default configuration
        self.plugin_dirs: list[Path] = []
        self.enabled_languages: set[str] | None = None
        self.default_plugin_config: PluginConfig = PluginConfig()

        if config_path:
            self.load(config_path)

    @classmethod
    def find_config(cls, start_path: Path = Path.cwd()) -> Path | None:
        """Find configuration file starting from the given path."""
        current = start_path.resolve()

        while current != current.parent:
            for ext in cls.SUPPORTED_FORMATS:
                config_file = current / f"{cls.DEFAULT_CONFIG_FILENAME}{ext}"
                if config_file.exists():
                    return config_file

            current = current.parent

        # Check user home directory
        home = Path.home()
        for ext in cls.SUPPORTED_FORMATS:
            config_file = home / ".chunker" / f"config{ext}"
            if config_file.exists():
                return config_file

        return None

    def load(self, config_path: Path) -> None:
        """Load configuration from file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Determine format from extension
        ext = config_path.suffix.lower()

        try:
            with Path(config_path).open() as f:
                if ext == ".toml":
                    self.data = toml.load(f)
                elif ext in {".yaml", ".yml"}:
                    self.data = yaml.safe_load(f) or {}
                elif ext == ".json":
                    self.data = json.load(f)
                else:
                    raise ValueError(f"Unsupported config format: {ext}")

            self.config_path = config_path

            # Expand environment variables in the loaded data
            if self.use_env_vars:
                self.data = self._expand_env_vars(self.data)

            self._parse_config()

            # Apply environment variable overrides
            if self.use_env_vars:
                self._apply_env_overrides()

            logger.info("Loaded configuration from: %s", config_path)

        except (FileNotFoundError, OSError, SyntaxError) as e:
            logger.error("Failed to load config from %s: %s", config_path, e)
            raise

    def save(self, config_path: Path | None = None) -> None:
        """Save configuration to file."""
        if not config_path:
            config_path = self.config_path

        if not config_path:
            raise ValueError("No config path specified")

        config_path = Path(config_path)
        ext = config_path.suffix.lower()

        # Prepare data for saving
        save_data = self._prepare_save_data()

        try:
            with Path(config_path).open("w") as f:
                if ext == ".toml":
                    toml.dump(save_data, f)
                elif ext in {".yaml", ".yml"}:
                    yaml.safe_dump(save_data, f, default_flow_style=False)
                elif ext == ".json":
                    json.dump(save_data, f, indent=2)
                else:
                    raise ValueError(f"Unsupported config format: {ext}")

            logger.info("Saved configuration to: %s", config_path)

        except (AttributeError, FileNotFoundError, KeyError) as e:
            logger.error("Failed to save config to %s: %s", config_path, e)
            raise

    def _parse_config(self) -> None:
        """Parse loaded configuration data."""
        # Parse chunker section
        chunker_config = self.data.get("chunker", {})

        # Plugin directories
        plugin_dirs = chunker_config.get("plugin_dirs", [])
        self.plugin_dirs = [self._resolve_path(p) for p in plugin_dirs]

        # Enabled languages
        enabled = chunker_config.get("enabled_languages")
        if enabled:
            self.enabled_languages = set(enabled)

        # Default plugin config
        default_config = chunker_config.get("default_plugin_config", {})
        self.default_plugin_config = self._parse_plugin_config(default_config)

        # Language-specific configurations
        languages = self.data.get("languages", {})
        for lang, config in languages.items():
            self.plugin_configs[lang] = self._parse_plugin_config(config)

    def _parse_plugin_config(self, config_dict: dict[str, Any]) -> PluginConfig:
        """Parse a plugin configuration dictionary."""
        # Extract known fields
        enabled = config_dict.get("enabled", True)
        chunk_types = config_dict.get("chunk_types")
        if chunk_types:
            chunk_types = set(chunk_types)

        min_chunk_size = config_dict.get("min_chunk_size", 1)
        max_chunk_size = config_dict.get("max_chunk_size")

        # Everything else goes to custom_options
        custom_options = {}
        known_fields = {"enabled", "chunk_types", "min_chunk_size", "max_chunk_size"}
        for key, value in config_dict.items():
            if key not in known_fields:
                custom_options[key] = value

        return PluginConfig(
            enabled=enabled,
            chunk_types=chunk_types,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            custom_options=custom_options,
        )

    def _prepare_save_data(self) -> dict[str, Any]:
        """Prepare configuration data for saving."""
        data = {}

        # Chunker section
        chunker = {}
        if self.plugin_dirs:
            chunker["plugin_dirs"] = [str(p) for p in self.plugin_dirs]

        if self.enabled_languages:
            chunker["enabled_languages"] = sorted(self.enabled_languages)

        # Default plugin config
        if self.default_plugin_config != PluginConfig():
            chunker["default_plugin_config"] = self._plugin_config_to_dict(
                self.default_plugin_config,
            )

        if chunker:
            data["chunker"] = chunker

        # Language configurations
        if self.plugin_configs:
            languages = {}
            for lang, config in sorted(self.plugin_configs.items()):
                languages[lang] = self._plugin_config_to_dict(config)
            data["languages"] = languages

        return data

    def _plugin_config_to_dict(self, config: PluginConfig) -> dict[str, Any]:
        """Convert PluginConfig to dictionary."""
        result = {}

        if not config.enabled:
            result["enabled"] = False

        if config.chunk_types:
            result["chunk_types"] = sorted(config.chunk_types)

        if config.min_chunk_size != 1:
            result["min_chunk_size"] = config.min_chunk_size

        if config.max_chunk_size:
            result["max_chunk_size"] = config.max_chunk_size

        # Add custom options
        result.update(config.custom_options)

        return result

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path string relative to config file location."""
        path = Path(path_str)

        # Expand user home
        if path_str.startswith("~"):
            return path.expanduser()

        # Absolute path
        if path.is_absolute():
            return path

        # Relative to config file
        if self.config_path:
            return (self.config_path.parent / path).resolve()

        # Relative to current directory
        return path.resolve()

    def get_plugin_config(self, language: str) -> PluginConfig:
        """Get configuration for a specific language plugin."""
        # Check if language is enabled
        if self.enabled_languages and language not in self.enabled_languages:
            return PluginConfig(enabled=False)

        # Return language-specific config or default
        return self.plugin_configs.get(language, self.default_plugin_config)

    def set_plugin_config(self, language: str, config: PluginConfig) -> None:
        """Set configuration for a specific language plugin."""
        self.plugin_configs[language] = config

    def add_plugin_directory(self, directory: Path) -> None:
        """Add a plugin directory."""
        directory = Path(directory).resolve()
        if directory not in self.plugin_dirs:
            self.plugin_dirs.append(directory)

    def remove_plugin_directory(self, directory: Path) -> None:
        """Remove a plugin directory."""
        directory = Path(directory).resolve()
        if directory in self.plugin_dirs:
            self.plugin_dirs.remove(directory)

    @classmethod
    def create_example_config(cls, config_path: Path) -> None:
        """Create an example configuration file."""
        example_data = {
            "chunker": {
                "plugin_dirs": ["./plugins", "~/.chunker/plugins"],
                "enabled_languages": ["python", "rust", "javascript", "c", "cpp"],
                "default_plugin_config": {
                    "min_chunk_size": 3,
                    "max_chunk_size": 500,
                },
            },
            "languages": {
                "python": {
                    "enabled": True,
                    "chunk_types": [
                        "function_definition",
                        "class_definition",
                        "async_function_definition",
                    ],
                    "include_docstrings": True,
                },
                "rust": {
                    "enabled": True,
                    "chunk_types": [
                        "function_item",
                        "impl_item",
                        "struct_item",
                        "enum_item",
                        "trait_item",
                    ],
                },
                "javascript": {
                    "enabled": True,
                    "chunk_types": [
                        "function_declaration",
                        "method_definition",
                        "class_declaration",
                        "arrow_function",
                    ],
                    "include_jsx": True,
                },
            },
        }

        config = cls()
        config.data = example_data
        config.save(config_path)

    def _expand_env_vars(self, data: Any) -> Any:
        """Recursively expand environment variables in configuration data.

        Supports ${VAR} and ${VAR:default} syntax.
        """
        if isinstance(data, str):
            # Find all environment variable references
            def replacer(match):
                var_expr = match.group(1)
                if ":" in var_expr:
                    var_name, default = var_expr.split(":", 1)
                else:
                    var_name, default = var_expr, None

                value = os.environ.get(var_name)
                if value is None:
                    if default is not None:
                        return default
                    logger.warning("Environment variable '%s' not found", var_name)
                    return match.group(0)  # Keep original
                return value

            return self.ENV_VAR_PATTERN.sub(replacer, data)

        if isinstance(data, dict):
            return {key: self._expand_env_vars(value) for key, value in data.items()}

        if isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]

        return data

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration.

        Environment variables with CHUNKER_ prefix override config values.
        Examples:
        - CHUNKER_ENABLED_LANGUAGES=python,rust
        - CHUNKER_PLUGIN_DIRS=/path/one,/path/two
        - CHUNKER_LANGUAGES_PYTHON_ENABLED=false
        """
        for env_var, value in os.environ.items():
            if not env_var.startswith(self.ENV_PREFIX):
                continue

            # Remove prefix and convert to config path
            config_path = env_var[len(self.ENV_PREFIX) :].lower()

            # Convert UPPER_SNAKE_CASE to nested dict path
            # e.g., LANGUAGES_PYTHON_ENABLED -> languages.python.enabled
            path_parts = config_path.split("_")

            # Special handling for known list types
            if config_path == "enabled_languages":
                self.enabled_languages = set(value.split(","))
                logger.info(
                    "Set enabled_languages from env: %s",
                    self.enabled_languages,
                )
                continue
            if config_path == "plugin_dirs":
                self.plugin_dirs = [Path(p.strip()) for p in value.split(",")]
                logger.info("Set plugin_dirs from env: %s", self.plugin_dirs)
                continue

            # Handle nested configuration
            if len(path_parts) >= 2 and path_parts[0] == "languages":
                # Language-specific config
                if len(path_parts) >= 3:
                    lang = path_parts[1]
                    setting = "_".join(path_parts[2:])

                    if lang not in self.plugin_configs:
                        self.plugin_configs[lang] = PluginConfig()

                    # Apply the setting
                    if setting == "enabled":
                        self.plugin_configs[lang].enabled = value.lower() == "true"
                    elif setting == "min_chunk_size":
                        self.plugin_configs[lang].min_chunk_size = int(value)
                    elif setting == "max_chunk_size":
                        self.plugin_configs[lang].max_chunk_size = int(value)
                    elif setting == "chunk_types":
                        self.plugin_configs[lang].chunk_types = set(value.split(","))
                    else:
                        # Custom option
                        self.plugin_configs[lang].custom_options[setting] = value

                    logger.info("Set %s.%s from env: %s", lang, setting, value)
            elif (
                len(path_parts) >= 2
                and path_parts[0] == "default"
                and path_parts[1] == "plugin"
                and path_parts[2] == "config"
            ):
                # Default plugin config
                setting = "_".join(path_parts[3:])
                if setting == "min_chunk_size":
                    self.default_plugin_config.min_chunk_size = int(value)
                elif setting == "max_chunk_size":
                    self.default_plugin_config.max_chunk_size = int(value)

                logger.info("Set default_plugin_config.%s from env: %s", setting, value)

    @classmethod
    def get_env_var_info(cls) -> dict[str, str]:
        """Get information about supported environment variables."""
        return {
            f"{cls.ENV_PREFIX}ENABLED_LANGUAGES": "Comma-separated list of enabled languages",
            f"{cls.ENV_PREFIX}PLUGIN_DIRS": "Comma-separated list of plugin directories",
            f"{cls.ENV_PREFIX}LANGUAGES_<LANG>_ENABLED": "Enable/disable specific language (true/false)",
            f"{cls.ENV_PREFIX}LANGUAGES_<LANG>_MIN_CHUNK_SIZE": "Minimum chunk size for language",
            f"{cls.ENV_PREFIX}LANGUAGES_<LANG>_MAX_CHUNK_SIZE": "Maximum chunk size for language",
            f"{cls.ENV_PREFIX}LANGUAGES_<LANG>_CHUNK_TYPES": "Comma-separated list of chunk types",
            f"{cls.ENV_PREFIX}DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE": "Default minimum chunk size",
            f"{cls.ENV_PREFIX}DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE": "Default maximum chunk size",
        }
