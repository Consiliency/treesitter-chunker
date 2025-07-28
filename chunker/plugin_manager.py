from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .languages.plugin_base import LanguagePlugin
from .parser import get_parser

if TYPE_CHECKING:
    from .languages.base import PluginConfig

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for managing language plugins."""

    def __init__(self):
        self._plugins: dict[str, type[LanguagePlugin]] = {}
        self._instances: dict[str, LanguagePlugin] = {}
        self._extension_map: dict[str, str] = {}  # .py -> python

    def register(self, plugin_class: type[LanguagePlugin]) -> None:
        """Register a plugin class."""
        if not issubclass(plugin_class, LanguagePlugin):
            raise TypeError(f"{plugin_class} must be a subclass of LanguagePlugin")

        # Create temporary instance to get metadata
        try:
            temp_instance = plugin_class()
        except Exception as e:
            raise RuntimeError(
                f"Failed to instantiate plugin {plugin_class.__name__}: {e}",
            )

        language = temp_instance.language_name
        metadata = temp_instance.plugin_metadata

        # Check for conflicts
        if language in self._plugins:
            existing_class = self._plugins[language]
            existing_instance = existing_class()
            existing_metadata = existing_instance.plugin_metadata

            logger.warning(
                f"Overriding existing plugin for language '{language}': "
                f"{existing_metadata['name']} v{existing_metadata['version']} -> "
                f"{metadata['name']} v{metadata['version']}",
            )

        # Check for extension conflicts
        extension_conflicts = []
        for ext in temp_instance.supported_extensions:
            if ext in self._extension_map and self._extension_map[ext] != language:
                extension_conflicts.append(
                    f"{ext} (currently mapped to {self._extension_map[ext]})",
                )

        if extension_conflicts:
            logger.info(
                f"Plugin {metadata['name']} for language '{language}' "
                f"shares extensions with other languages: {', '.join(extension_conflicts)}. "
                f"Content-based detection will be used for .h files.",
            )

        self._plugins[language] = plugin_class

        # Update extension mapping
        for ext in temp_instance.supported_extensions:
            self._extension_map[ext] = language

        logger.info(
            f"Registered plugin {metadata['name']} v{metadata['version']} "
            f"for language '{language}' with extensions: {list(temp_instance.supported_extensions)}",
        )

    def unregister(self, language: str) -> None:
        """Unregister a plugin."""
        if language in self._plugins:
            # Remove from extension map
            plugin_class = self._plugins[language]
            temp_instance = plugin_class()
            for ext in temp_instance.supported_extensions:
                self._extension_map.pop(ext, None)

            # Remove plugin
            self._plugins.pop(language)
            self._instances.pop(language, None)
            logger.info("Unregistered plugin for language: %s", language)

    def get_plugin(
        self,
        language: str,
        config: PluginConfig | None = None,
    ) -> LanguagePlugin:
        """Get or create a plugin instance."""
        if language not in self._plugins:
            raise ValueError(f"No plugin registered for language: {language}")

        # Return cached instance if config hasn't changed
        if language in self._instances and config is None:
            return self._instances[language]

        # Create new instance
        plugin_class = self._plugins[language]
        instance = plugin_class(config)

        # Set up parser
        try:
            parser = get_parser(language)
            instance.set_parser(parser)
        except Exception as e:
            logger.error("Failed to set parser for %s: %s", language, e)
            raise

        # Cache if using default config
        if config is None:
            self._instances[language] = instance

        return instance

    def get_language_for_file(self, file_path: Path) -> str | None:
        """Determine language from file extension."""
        ext = file_path.suffix.lower()
        return self._extension_map.get(ext)

    def list_languages(self) -> list[str]:
        """List all registered languages."""
        return list(self._plugins.keys())

    def list_extensions(self) -> dict[str, str]:
        """List all supported file extensions and their languages."""
        return self._extension_map.copy()


class PluginManager:
    """Manager for discovering and loading plugins."""

    def __init__(self):
        self.registry = PluginRegistry()
        self._plugin_dirs: list[Path] = []
        self._loaded_modules: set[str] = set()

    def add_plugin_directory(self, directory: Path) -> None:
        """Add a directory to search for plugins."""
        directory = Path(directory).resolve()
        if directory.exists() and directory.is_dir():
            self._plugin_dirs.append(directory)
            logger.info("Added plugin directory: %s", directory)
        else:
            logger.warning("Plugin directory does not exist: %s", directory)

    def discover_plugins(
        self,
        directory: Path | None = None,
    ) -> list[type[LanguagePlugin]]:
        """Discover plugin classes in a directory."""
        plugins: list[type[LanguagePlugin]] = []

        if directory:
            search_dirs = [Path(directory)]
        else:
            search_dirs = self._plugin_dirs

        for plugin_dir in search_dirs:
            if not plugin_dir.exists():
                continue

            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_") or py_file.name == "base.py":
                    continue

                try:
                    plugin_classes = self._load_plugin_from_file(py_file)
                    plugins.extend(plugin_classes)
                except Exception as e:
                    logger.error("Failed to load plugin from %s: %s", py_file, e)

        return plugins

    def _load_plugin_from_file(self, file_path: Path) -> list[type[LanguagePlugin]]:
        """Load plugin classes from a Python file."""
        # Create unique module name
        module_name = f"chunker_plugin_{file_path.stem}_{id(file_path)}"

        if module_name in self._loaded_modules:
            return []

        # For builtin plugins, use regular import instead of dynamic loading
        if str(file_path).startswith(str(Path(__file__).parent / "languages")):
            # Use relative import for builtin plugins
            try:
                if file_path.stem == "base":
                    return []  # Skip base module

                # Import the module normally
                module = importlib.import_module(f"chunker.languages.{file_path.stem}")

                # Find all LanguagePlugin subclasses
                plugins = []
                for _name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, LanguagePlugin)
                        and obj is not LanguagePlugin
                        and not inspect.isabstract(obj)
                    ):
                        plugins.append(obj)
                        logger.info(
                            f"Found plugin class: {obj.__name__} in {file_path}",
                        )

                return plugins
            except ImportError as e:
                logger.error("Failed to import builtin plugin %s: %s", file_path.stem, e)
                return []

        # For external plugins, use dynamic loading
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load module from {file_path}")

            module = importlib.util.module_from_spec(spec)

            # Add parent modules to sys.modules for relative imports
            sys.modules[module_name] = module

            # Set up parent package for relative imports
            if file_path.parent.name == "languages":
                module.__package__ = "chunker.languages"

            spec.loader.exec_module(module)

            self._loaded_modules.add(module_name)

            # Find all LanguagePlugin subclasses
            plugins = []
            for _name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, LanguagePlugin)
                    and obj is not LanguagePlugin
                    and not inspect.isabstract(obj)
                ):
                    plugins.append(obj)
                    logger.info("Found plugin class: %s in %s", obj.__name__, file_path)

            return plugins
        except Exception as e:
            logger.error("Failed to load plugin from %s: %s", file_path, e)
            return []

    def load_builtin_plugins(self) -> None:
        """Load plugins from the built-in languages directory."""
        builtin_dir = Path(__file__).parent / "languages"
        self.add_plugin_directory(builtin_dir)
        plugins = self.discover_plugins(builtin_dir)

        for plugin_class in plugins:
            try:
                self.registry.register(plugin_class)
            except Exception as e:
                logger.error("Failed to register %s: %s", plugin_class.__name__, e)

    def load_plugins_from_directory(self, directory: Path) -> int:
        """Load all plugins from a directory."""
        self.add_plugin_directory(directory)
        plugins = self.discover_plugins(directory)

        loaded = 0
        for plugin_class in plugins:
            try:
                self.registry.register(plugin_class)
                loaded += 1
            except Exception as e:
                logger.error("Failed to register %s: %s", plugin_class.__name__, e)

        return loaded

    def get_plugin(
        self,
        language: str,
        config: PluginConfig | None = None,
    ) -> LanguagePlugin:
        """Get a plugin instance."""
        return self.registry.get_plugin(language, config)

    def _detect_h_file_language(self, file_path: Path) -> str | None:
        """Detect if .h file is C or C++ based on content."""
        try:
            content = file_path.read_text(errors="ignore")

            # C++ indicators
            cpp_patterns = [
                r"\bclass\s+\w+\s*[:{]",
                r"\bnamespace\s+\w+",
                r"\btemplate\s*<",
                r"\busing\s+namespace\s+",
                r"\bpublic\s*:",
                r"\bprivate\s*:",
                r"\bprotected\s*:",
                r"std::",
                r"\bvirtual\s+",
                r"\boverride\b",
                r"\bfinal\b",
                r"#include\s*<\w+>",  # STL headers without .h
            ]

            for pattern in cpp_patterns:
                if re.search(pattern, content):
                    return "cpp"

            return "c"  # Default to C if no C++ features found
        except Exception as e:
            logger.debug("Could not detect language for %s: %s", file_path, e)
            return None  # Detection failed

    def chunk_file(
        self,
        file_path: Path,
        language: str | None = None,
        config: PluginConfig | None = None,
    ) -> list[Any]:
        """Chunk a file using the appropriate plugin."""
        file_path = Path(file_path)

        # Determine language
        if not language:
            # First try: extension mapping
            language = self.registry.get_language_for_file(file_path)

            # Special handling for ambiguous extensions
            if file_path.suffix.lower() == ".h":
                detected_lang = self._detect_h_file_language(file_path)
                if detected_lang:
                    language = detected_lang
                    logger.info("Detected %s as %s based on content", file_path, language)
                # Detection failed, keep the registry default (C)
                elif language:
                    logger.info(
                        f"Could not detect language for {file_path}, defaulting to {language}",
                    )

            if not language:
                raise ValueError(
                    f"Cannot determine language for file: {file_path}. "
                    f"Please specify language explicitly.",
                )

        # Get plugin and chunk
        plugin = self.get_plugin(language, config)
        return plugin.chunk_file(file_path)


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.load_builtin_plugins()
    return _plugin_manager
