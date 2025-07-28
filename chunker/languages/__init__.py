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
from .clojure import ClojurePlugin
from .cpp import CppPlugin
from .dart import DartPlugin

# Import Tier 2 language plugins
from .dockerfile import DockerfilePlugin
from .elixir import ElixirPlugin
from .go_plugin import GoPlugin

# Import Tier 3 language plugins
from .haskell import HaskellPlugin
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
from .scala import ScalaPlugin
from .sql import SQLPlugin
from .svelte import SveltePlugin
from .vue import VuePlugin

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
    # Tier 3 languages
    "HaskellPlugin",
    "ScalaPlugin",
    "ElixirPlugin",
    "ClojurePlugin",
    "DartPlugin",
    "VuePlugin",
    "SveltePlugin",
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

# Auto-import Tier 3 language configurations
try:
    from . import haskell  # noqa: F401
except ImportError:
    pass

try:
    from . import scala  # noqa: F401
except ImportError:
    pass

try:
    from . import elixir  # noqa: F401
except ImportError:
    pass

try:
    from . import clojure  # noqa: F401
except ImportError:
    pass

try:
    from . import dart  # noqa: F401
except ImportError:
    pass

try:
    from . import vue  # noqa: F401
except ImportError:
    pass

try:
    from . import svelte  # noqa: F401
except ImportError:
    pass
