"""
Per-language helpers live here (e.g. node-type mappings, heuristics).
"""

# ruff: noqa: SIM105

# Phase 2.1 exports (LanguageConfig system)

from . import (
    clojure,
    dart,
    dockerfile,
    elixir,
    go_plugin,
    haskell,
    java_plugin,
    julia,
    matlab,
    nasm,
    ocaml,
    python,
    r,
    ruby_plugin,
    scala,
    sql,
    svelte,
    toml,
    vue,
    wasm,
    xml,
    yaml,
    zig,
)
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

# Import Tier 1 language plugins
from .java_plugin import JavaPlugin
from .javascript import JavaScriptPlugin
from .julia import JuliaPlugin
from .matlab import MATLABPlugin

# Import Tier 4 language plugins
from .nasm import NASMPlugin
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
from .toml import TOMLPlugin
from .vue import VuePlugin
from .wasm import WASMPlugin
from .xml import XMLPlugin
from .yaml import YAMLPlugin
from .zig import ZigPlugin

_plugin_exports = [
    "PythonPlugin",
    "RustPlugin",
    "JavaScriptPlugin",
    "CPlugin",
    "CppPlugin",
    "GoPlugin",
    "RubyPlugin",
    "JavaPlugin",
    # Tier 1 languages
    "TOMLPlugin",
    "XMLPlugin",
    "YAMLPlugin",
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
    # Tier 4 languages
    "ZigPlugin",
    "NASMPlugin",
    "WASMPlugin",
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
    # Plugin exports
    *_plugin_exports,
]

# Auto-import language configurations to register them
try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

# Auto-import Tier 1 language configurations
try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

# Auto-import Tier 2 language configurations
try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

# Auto-import Tier 3 language configurations
try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

# Auto-import Tier 4 language configurations
try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass
