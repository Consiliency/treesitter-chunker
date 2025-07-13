from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import toml
import yaml

from .languages.base import PluginConfig

logger = logging.getLogger(__name__)


class ChunkerConfig:
    """Configuration manager for the chunker system."""
    
    DEFAULT_CONFIG_FILENAME = "chunker.config"
    SUPPORTED_FORMATS = {".toml", ".yaml", ".yml", ".json"}
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.data: Dict[str, Any] = {}
        self.plugin_configs: Dict[str, PluginConfig] = {}
        
        # Default configuration
        self.plugin_dirs: List[Path] = []
        self.enabled_languages: Optional[Set[str]] = None
        self.default_plugin_config: PluginConfig = PluginConfig()
        
        if config_path:
            self.load(config_path)
            
    @classmethod
    def find_config(cls, start_path: Path = Path.cwd()) -> Optional[Path]:
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
            with open(config_path, 'r') as f:
                if ext == '.toml':
                    self.data = toml.load(f)
                elif ext in {'.yaml', '.yml'}:
                    self.data = yaml.safe_load(f) or {}
                elif ext == '.json':
                    self.data = json.load(f)
                else:
                    raise ValueError(f"Unsupported config format: {ext}")
                    
            self.config_path = config_path
            self._parse_config()
            logger.info(f"Loaded configuration from: {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise
            
    def save(self, config_path: Optional[Path] = None) -> None:
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
            with open(config_path, 'w') as f:
                if ext == '.toml':
                    toml.dump(save_data, f)
                elif ext in {'.yaml', '.yml'}:
                    yaml.safe_dump(save_data, f, default_flow_style=False)
                elif ext == '.json':
                    json.dump(save_data, f, indent=2)
                else:
                    raise ValueError(f"Unsupported config format: {ext}")
                    
            logger.info(f"Saved configuration to: {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
            raise
            
    def _parse_config(self) -> None:
        """Parse loaded configuration data."""
        # Parse chunker section
        chunker_config = self.data.get('chunker', {})
        
        # Plugin directories
        plugin_dirs = chunker_config.get('plugin_dirs', [])
        self.plugin_dirs = [self._resolve_path(p) for p in plugin_dirs]
        
        # Enabled languages
        enabled = chunker_config.get('enabled_languages')
        if enabled:
            self.enabled_languages = set(enabled)
            
        # Default plugin config
        default_config = chunker_config.get('default_plugin_config', {})
        self.default_plugin_config = self._parse_plugin_config(default_config)
        
        # Language-specific configurations
        languages = self.data.get('languages', {})
        for lang, config in languages.items():
            self.plugin_configs[lang] = self._parse_plugin_config(config)
            
    def _parse_plugin_config(self, config_dict: Dict[str, Any]) -> PluginConfig:
        """Parse a plugin configuration dictionary."""
        # Extract known fields
        enabled = config_dict.get('enabled', True)
        chunk_types = config_dict.get('chunk_types')
        if chunk_types:
            chunk_types = set(chunk_types)
            
        min_chunk_size = config_dict.get('min_chunk_size', 1)
        max_chunk_size = config_dict.get('max_chunk_size')
        
        # Everything else goes to custom_options
        custom_options = {}
        known_fields = {'enabled', 'chunk_types', 'min_chunk_size', 'max_chunk_size'}
        for key, value in config_dict.items():
            if key not in known_fields:
                custom_options[key] = value
                
        return PluginConfig(
            enabled=enabled,
            chunk_types=chunk_types,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            custom_options=custom_options
        )
        
    def _prepare_save_data(self) -> Dict[str, Any]:
        """Prepare configuration data for saving."""
        data = {}
        
        # Chunker section
        chunker = {}
        if self.plugin_dirs:
            chunker['plugin_dirs'] = [str(p) for p in self.plugin_dirs]
            
        if self.enabled_languages:
            chunker['enabled_languages'] = sorted(self.enabled_languages)
            
        # Default plugin config
        if self.default_plugin_config != PluginConfig():
            chunker['default_plugin_config'] = self._plugin_config_to_dict(
                self.default_plugin_config
            )
            
        if chunker:
            data['chunker'] = chunker
            
        # Language configurations
        if self.plugin_configs:
            languages = {}
            for lang, config in sorted(self.plugin_configs.items()):
                languages[lang] = self._plugin_config_to_dict(config)
            data['languages'] = languages
            
        return data
        
    def _plugin_config_to_dict(self, config: PluginConfig) -> Dict[str, Any]:
        """Convert PluginConfig to dictionary."""
        result = {}
        
        if not config.enabled:
            result['enabled'] = False
            
        if config.chunk_types:
            result['chunk_types'] = sorted(config.chunk_types)
            
        if config.min_chunk_size != 1:
            result['min_chunk_size'] = config.min_chunk_size
            
        if config.max_chunk_size:
            result['max_chunk_size'] = config.max_chunk_size
            
        # Add custom options
        result.update(config.custom_options)
        
        return result
        
    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path string relative to config file location."""
        path = Path(path_str)
        
        # Expand user home
        if path_str.startswith('~'):
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
                    "max_chunk_size": 500
                }
            },
            "languages": {
                "python": {
                    "enabled": True,
                    "chunk_types": [
                        "function_definition",
                        "class_definition",
                        "async_function_definition"
                    ],
                    "include_docstrings": True
                },
                "rust": {
                    "enabled": True,
                    "chunk_types": [
                        "function_item",
                        "impl_item",
                        "struct_item",
                        "enum_item",
                        "trait_item"
                    ]
                },
                "javascript": {
                    "enabled": True,
                    "chunk_types": [
                        "function_declaration",
                        "method_definition",
                        "class_declaration",
                        "arrow_function"
                    ],
                    "include_jsx": True
                }
            }
        }
        
        config = cls()
        config.data = example_data
        config.save(config_path)