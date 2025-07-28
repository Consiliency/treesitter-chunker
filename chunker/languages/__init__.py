"""
Per‑language helpers live here (e.g. node‑type mappings, heuristics).
"""

# Phase 2.1 exports (LanguageConfig system)
from .base import (
    ChunkRule,
    CompositeLanguageConfig,
    LanguageConfig,
    LanguageConfigRegistry,
    PluginConfig,  # For backward compatibility
    language_config_registry,
    validate_language_config,
)
from .c import CPlugin
from .cpp import CppPlugin

# Import Tier 2 language plugins
from .dockerfile import DockerfilePlugin
from .go_plugin import GoPlugin
from .java_plugin import JavaPlugin
from .javascript import JavaScriptPlugin
from .julia import JuliaPlugin
from .matlab import MATLABPlugin
from .ocaml import OCamlPlugin

# Phase 1.2 exports (Plugin system)
from .plugin_base import LanguagePlugin

# Import plugin implementations
from .python import PythonPlugin
from .r import RPlugin
from .ruby_plugin import RubyPlugin
from .rust import RustPlugin
from .sql import SQLPlugin

_plugin_exports = [
    "PythonPlugin",
    "RustPlugin",
    "JavaScriptPlugin",
    "CPlugin",
    "CppPlugin",
    "GoPlugin",
    "RubyPlugin",
    "JavaPlugin",
    # Tier 2 languages
    "DockerfilePlugin",
    "SQLPlugin",
    "MATLABPlugin",
    "RPlugin",
    "JuliaPlugin",
    "OCamlPlugin",
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

try:
    from . import go_plugin  # noqa: F401
except ImportError:
    pass

try:
    from . import ruby_plugin  # noqa: F401
except ImportError:
    pass

try:
    from . import java_plugin  # noqa: F401
except ImportError:
    pass

# Auto-import Tier 2 language configurations
try:
    from . import dockerfile  # noqa: F401
except ImportError:
    pass

try:
    from . import sql  # noqa: F401
except ImportError:
    pass

try:
    from . import matlab  # noqa: F401
except ImportError:
    pass

try:
    from . import r  # noqa: F401
except ImportError:
    pass

try:
    from . import julia  # noqa: F401
except ImportError:
    pass

try:
    from . import ocaml  # noqa: F401
except ImportError:
    pass
