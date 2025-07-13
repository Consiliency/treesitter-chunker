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

# Try to import plugin implementations if available
_plugin_exports = []
try:
    from .python import PythonPlugin
    _plugin_exports.append("PythonPlugin")
except ImportError:
    pass

try:
    from .rust import RustPlugin
    _plugin_exports.append("RustPlugin")
except ImportError:
    pass

try:
    from .javascript import JavaScriptPlugin
    _plugin_exports.append("JavaScriptPlugin")
except ImportError:
    pass

try:
    from .c import CPlugin
    _plugin_exports.append("CPlugin")
except ImportError:
    pass

try:
    from .cpp import CppPlugin
    _plugin_exports.append("CppPlugin")
except ImportError:
    pass

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
