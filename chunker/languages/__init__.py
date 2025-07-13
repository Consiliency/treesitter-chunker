"""
Per‑language helpers live here (e.g. node‑type mappings, heuristics).
"""

# Phase 2.1 exports (LanguageConfig system)
from .base import (
    LanguageConfig,
    CompositeLanguageConfig,
    ChunkRule,
    LanguageConfigRegistry,
    language_config_registry,
    validate_language_config,
    PluginConfig,  # For backward compatibility
)

# Phase 1.2 exports (Plugin system)
from .plugin_base import LanguagePlugin

# Import plugin implementations
from .python import PythonPlugin
from .rust import RustPlugin
from .javascript import JavaScriptPlugin
from .c import CPlugin
from .cpp import CppPlugin

_plugin_exports = [
    "PythonPlugin",
    "RustPlugin", 
    "JavaScriptPlugin",
    "CPlugin",
    "CppPlugin",
]

__all__ = [
    # Phase 2.1 exports
    "LanguageConfig",
    "CompositeLanguageConfig",
    "ChunkRule",
    "LanguageConfigRegistry",
    "language_config_registry",
    "validate_language_config",
    # Phase 1.2 exports
    "LanguagePlugin",
    "PluginConfig",
] + _plugin_exports

# Auto-import language configurations to register them
try:
    from . import python  # noqa: F401
except ImportError:
    pass
