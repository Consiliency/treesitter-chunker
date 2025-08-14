"""Base language configuration framework for tree-sitter-chunker.

This module provides the foundational classes and interfaces for defining
language-specific chunking configurations.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChunkRule:
    """Defines a rule for identifying chunks in the AST.

    Attributes:
        node_types: Set of tree-sitter node types that match this rule
        include_children: Whether to include child nodes in the chunk
        priority: Priority when multiple rules match (higher = higher priority)
        metadata: Additional metadata for the rule
    """

    node_types: set[str]
    include_children: bool = True
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Human-friendly rule name from metadata or inferred from node types."""
        if "name" in self.metadata and isinstance(self.metadata["name"], str):
            return self.metadata["name"]
        # Fallback: join node types for a readable name
        try:
            return ",".join(sorted(self.node_types))
        except Exception:
            return "rule"


@dataclass
class PluginConfig:
    """Configuration for a language plugin."""

    enabled: bool = True
    chunk_types: set[str] | None = None
    min_chunk_size: int = 1
    max_chunk_size: int | None = None
    custom_options: dict[str, Any] = None

    def __post_init__(self):
        if self.custom_options is None:
            self.custom_options = {}


class LanguageConfig(ABC):
    """Abstract base class for language-specific configurations.

    This class defines the interface that all language configurations must
    implement. It provides common functionality for chunk identification,
    node filtering, and configuration validation.
    """

    def __init__(self):
        """Initialize the language configuration."""
        self._chunk_rules: list[ChunkRule] = []
        self._ignore_types: set[str] = set()
        self._validate_config()

    @property
    @abstractmethod
    def language_id(self) -> str:
        """Return the unique identifier for this language (e.g., 'python', 'rust')."""

    @property
    def name(self) -> str:
        """Human-friendly language name. Defaults to `language_id`.

        Subclasses may override this to expose a canonical display name that
        can differ from `language_id` (e.g., 'csharp' vs 'c_sharp').
        """
        return self.language_id

    @property
    @abstractmethod
    def chunk_types(self) -> set[str]:
        """Return the set of node types that should be treated as chunks.

        This is the primary set of node types that will be extracted as
        independent chunks from the AST.
        """

    @property
    def ignore_types(self) -> set[str]:
        """Return the set of node types that should be ignored during traversal.

        These nodes and their children will be skipped during chunk extraction.
        """
        return self._ignore_types

    @property
    def file_extensions(self) -> set[str]:
        """Return the set of file extensions associated with this language."""
        return set()

    @property
    def chunk_rules(self) -> list[ChunkRule]:
        """Return advanced chunking rules for more complex scenarios."""
        return self._chunk_rules

    @property
    def scope_node_types(self) -> set[str]:
        """Optional set of scope node types if the config defines them."""
        return getattr(self, "_scope_node_types", set())

    def should_chunk_node(
        self,
        node_type: str,
        _parent_type: str | None = None,
    ) -> bool:
        """Determine if a node should be treated as a chunk.

        Args:
            node_type: The type of the current node
            parent_type: The type of the parent node (if any)

        Returns:
            True if the node should be a chunk, False otherwise
        """
        if node_type in self.ignore_types:
            return False
        if node_type in self.chunk_types:
            return True
        return any(node_type in rule.node_types for rule in self.chunk_rules)

    def should_ignore_node(self, node_type: str) -> bool:
        """Determine if a node should be ignored during traversal.

        Args:
            node_type: The type of the node to check

        Returns:
            True if the node should be ignored, False otherwise
        """
        return node_type in self.ignore_types

    def get_chunk_metadata(self, node_type: str) -> dict[str, Any]:
        """Get metadata for a specific chunk type.

        Args:
            node_type: The type of the chunk node

        Returns:
            Dictionary of metadata for the chunk type
        """
        for rule in self.chunk_rules:
            if node_type in rule.node_types:
                return rule.metadata
        return {}

    def add_chunk_rule(self, rule: ChunkRule) -> None:
        """Add an advanced chunking rule.

        Args:
            rule: The ChunkRule to add
        """
        self._chunk_rules.append(rule)
        self._chunk_rules.sort(key=lambda r: r.priority, reverse=True)

    def add_ignore_type(self, node_type: str) -> None:
        """Add a node type to the ignore list.

        Args:
            node_type: The node type to ignore
        """
        self._ignore_types.add(node_type)

    def _validate_config(self) -> None:
        """Validate the configuration.

        This method is called during initialization to ensure the
        configuration is valid. Subclasses can override this to add
        custom validation logic.
        """
        overlap = self.chunk_types & self.ignore_types
        if overlap:
            raise ValueError(
                f"Configuration error: Node types cannot be both chunk types and ignore types: {overlap}",
            )

    def __repr__(self) -> str:
        """Return a string representation of the configuration."""
        return f"{self.__class__.__name__}(language_id={self.language_id!r}, chunk_types={len(self.chunk_types)}, ignore_types={len(self.ignore_types)}, rules={len(self.chunk_rules)})"


# Backward compatibility alias expected by older plugins/tests
class LanguageChunker(LanguageConfig):
    """Compatibility shim: some plugins import LanguageChunker from languages.base."""

    @property
    def language_id(self) -> str:  # pragma: no cover - only for legacy imports
        return "generic"

    @property
    def chunk_types(self) -> set[str]:  # pragma: no cover
        return set()


class CompositeLanguageConfig(LanguageConfig):
    """A language configuration that inherits from one or more parent configs.

    This class enables configuration inheritance for language families,
    allowing languages like C++ to inherit from C while adding their own
    specific configurations.
    """

    def __init__(self, *parent_configs: LanguageConfig):
        """Initialize with parent configurations.

        Args:
            parent_configs: Parent configurations to inherit from
        """
        self._parent_configs = list(parent_configs)
        self._own_chunk_types: set[str] = set()
        self._own_ignore_types: set[str] = set()
        super().__init__()

    @property
    def chunk_types(self) -> set[str]:
        """Return merged chunk types from all parent configs plus own types."""
        types = self._own_chunk_types.copy()
        for parent in self._parent_configs:
            types.update(parent.chunk_types)
        return types

    @property
    def ignore_types(self) -> set[str]:
        """Return merged ignore types from all parent configs plus own types."""
        types = self._own_ignore_types.copy()
        for parent in self._parent_configs:
            types.update(parent.ignore_types)
        return types

    @property
    def chunk_rules(self) -> list[ChunkRule]:
        """Return merged chunk rules from all parent configs plus own rules."""
        rules = [item for parent in self._parent_configs for item in parent.chunk_rules]
        rules.extend(self._chunk_rules)
        rules.sort(key=lambda r: r.priority, reverse=True)
        return rules

    def add_chunk_type(self, node_type: str) -> None:
        """Add a chunk type specific to this configuration.

        Args:
            node_type: The node type to add as a chunk type
        """
        self._own_chunk_types.add(node_type)

    def add_ignore_type(self, node_type: str) -> None:
        """Add an ignore type specific to this configuration.

        Args:
            node_type: The node type to add to ignore list
        """
        self._own_ignore_types.add(node_type)

    def add_parent(self, parent_config: LanguageConfig) -> None:
        """Add a parent configuration to inherit from.

        Args:
            parent_config: The parent configuration to add
        """
        self._parent_configs.append(parent_config)
        self._validate_config()


def validate_language_config(config: LanguageConfig) -> list[str]:
    """Validate a language configuration and return any issues found.

    Args:
        config: The language configuration to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    if not config.language_id:
        errors.append("Language ID cannot be empty")
    if not config.chunk_types:
        errors.append("Configuration must define at least one chunk type")
    for node_type in config.chunk_types | config.ignore_types:
        if not node_type or not isinstance(node_type, str):
            errors.append(f"Invalid node type: {node_type!r}")
        elif " " in node_type:
            errors.append(f"Node type cannot contain spaces: {node_type!r}")
    overlap = config.chunk_types & config.ignore_types
    if overlap:
        errors.append(f"Node types cannot be both chunk and ignore types: {overlap}")
    for i, rule in enumerate(config.chunk_rules):
        if not rule.node_types:
            errors.append(f"Chunk rule {i} has no node types defined")
        if rule.priority < 0:
            errors.append(f"Chunk rule {i} has negative priority: {rule.priority}")
    return errors


class LanguageConfigRegistry:
    """Registry for managing language configurations.

    This class provides a central place to register and retrieve
    language configurations.
    """

    def __init__(self, enable_lazy_loading: bool = True):
        """Initialize the registry."""
        self._configs: dict[str, LanguageConfig] = {}
        self._aliases: dict[str, str] = {}
        self._enable_lazy_loading = enable_lazy_loading

    def register(
        self,
        config: LanguageConfig,
        aliases: list[str] | None = None,
    ) -> None:
        """Register a language configuration.

        Args:
            config: The language configuration to register
            aliases: Optional list of aliases for the language

        Raises:
            ValueError: If the configuration is invalid or language ID already registered
        """
        errors = validate_language_config(config)
        if errors:
            raise ValueError(
                f"Invalid configuration for {config.language_id}: " + "; ".join(errors),
            )
        if config.language_id in self._configs:
            # For strict registry instances (used in tests), duplicate registration should fail
            if not self._enable_lazy_loading:
                raise ValueError(f"Language {config.language_id} is already registered")
            # In lazy-loading mode (default global registry), be idempotent to avoid noisy errors
            existing = self._configs[config.language_id]
            if type(existing) is type(config):
                return
            # Replace existing with new config to allow dynamic upgrades in lazy mode
            self._configs[config.language_id] = config
            return
        self._configs[config.language_id] = config
        logger.info(
            "Registered language configuration: %s",
            config.language_id,
        )
        if aliases:
            for alias in aliases:
                if alias in self._aliases:
                    raise ValueError(f"Alias {alias} is already registered")
                self._aliases[alias] = config.language_id

    def get(self, language_id: str) -> LanguageConfig | None:
        """Get a language configuration by ID or alias.

        Args:
            language_id: The language ID or alias

        Returns:
            The language configuration or None if not found
        """
        if language_id in self._aliases:
            language_id = self._aliases[language_id]
        config = self._configs.get(language_id)
        if config is None and self._enable_lazy_loading:
            # Attempt lazy re-registration if a test cleared the global registry
            self._lazy_register_by_language_id(language_id)
            # Resolve alias again in case lazy registration added it
            if language_id in self._aliases:
                language_id = self._aliases[language_id]
            config = self._configs.get(language_id)
        return config

    # Backward/compatibility alias used by tests
    def get_config(self, language_id: str) -> LanguageConfig | None:
        """Alias for get(language_id) for compatibility with tests and older API."""
        return self.get(language_id)

    def list_languages(self) -> list[str]:
        """List all registered language IDs."""
        return sorted(self._configs.keys())

    def get_for_file(self, file_name: str) -> LanguageConfig | None:
        """Get a language configuration by file extension.

        Args:
            file_name: Name of the file (used to match extension)

        Returns:
            The matching language configuration or None
        """
        import os

        _, ext = os.path.splitext(file_name.lower())
        if not ext:
            return None
        for config in self._configs.values():
            try:
                if ext in config.file_extensions:
                    return config
            except Exception:
                continue
        # Try to lazily register defaults for known extensions (e.g., after a
        # test cleared the global registry)
        if self._enable_lazy_loading:
            self._lazy_register_defaults_for_extension(ext)
            for config in self._configs.values():
                try:
                    if ext in config.file_extensions:
                        return config
                except Exception:
                    continue
        return None

    def _lazy_register_defaults_for_extension(self, ext: str) -> None:
        """Best-effort registration of default language configs for an extension.

        This is invoked when the registry is empty or missing configs because
        some tests clear the global registry. It only registers a minimal set
        needed by tests without importing all languages eagerly.
        """
        try:
            if ext in {".cs", ".csx"}:
                # Register C# on demand
                from .cs import CSharpConfig  # lazy import

                # Avoid duplicate registration errors
                if self.get("c_sharp") is None and self.get("csharp") is None:
                    self.register(CSharpConfig(), aliases=["csharp"])
            elif ext == ".go":
                # Register Go on demand
                from .go_plugin import GoConfig  # lazy import

                if self.get("go") is None:
                    self.register(GoConfig())
            elif ext in {".ts", ".d.ts", ".tsx"}:
                # Register TypeScript and TSX on demand
                from .typescript import TSXConfig as _TSXConfig
                from .typescript import TypeScriptConfig as _TSConfig  # lazy import

                if self.get("typescript") is None:
                    self.register(_TSConfig())
                if self.get("tsx") is None:
                    self.register(_TSXConfig())
            elif ext in {".php", ".php3", ".php4", ".php5", ".phtml"}:
                # Register PHP on demand
                from .php import PHPConfig  # lazy import

                if self.get("php") is None:
                    self.register(PHPConfig())
            elif ext in {".sql"}:
                # Register SQL on demand
                from .sql import SQLConfig  # lazy import

                if self.get("sql") is None:
                    self.register(SQLConfig())
            elif ext in {".ml", ".mli"}:
                # Register OCaml on demand
                from .ocaml import OCamlConfig  # lazy import

                if self.get("ocaml") is None:
                    self.register(OCamlConfig())
            elif ext in {".m"}:
                # Register MATLAB on demand
                from .matlab import MATLABConfig  # lazy import

                if self.get("matlab") is None:
                    self.register(MATLABConfig())
            elif ext in {".js", ".jsx"}:
                # Ensure JavaScript is registered
                from .javascript import JavaScriptConfig  # lazy import

                if self.get("javascript") is None:
                    self.register(JavaScriptConfig())
        except Exception:
            # Swallow errors to keep method safe to call during detection paths
            return

    def _lazy_register_by_language_id(self, language_id: str) -> None:
        """Best-effort registration by language id.

        Handles common aliases and registers minimal configs on demand.
        """
        try:
            # Handle special cases where module name differs from language id
            special: dict[str, tuple[str, str, list[str]]] = {
                # language_id: (module_name, class_name, aliases)
                "csharp": ("cs", "CSharpConfig", ["csharp"]),
                "c_sharp": ("cs", "CSharpConfig", ["csharp"]),
                "go": ("go_plugin", "GoConfig", []),
                "py": ("python", "PythonConfig", ["py", "python3"]),
                "python3": ("python", "PythonConfig", ["py", "python3"]),
                "javascript": ("javascript", "JavaScriptConfig", []),
                "typescript": ("typescript", "TypeScriptConfig", []),
                "tsx": ("typescript", "TSXConfig", []),
                "php": ("php", "PHPConfig", []),
                "sql": ("sql", "SQLConfig", []),
                "ocaml": ("ocaml", "OCamlConfig", []),
                "matlab": ("matlab", "MATLABConfig", []),
            }
            module_name: str
            class_name: str
            aliases: list[str]
            if language_id in special:
                module_name, class_name, aliases = special[language_id]
            else:
                module_name = language_id
                class_name = f"{language_id.capitalize()}Config"
                aliases = []

            module = __import__(
                f"{__package__}.{module_name}",
                fromlist=[class_name],
            )
            config_cls = getattr(module, class_name, None)
            if not config_cls:
                return
            # Avoid duplicate registration
            if self._configs.get(language_id) is None:
                self.register(config_cls(), aliases=aliases or None)
        except Exception:
            # Keep silent; fallback paths will handle missing configs
            return

    def clear(self) -> None:
        """Clear all registered configurations."""
        self._configs.clear()
        self._aliases.clear()


language_config_registry = LanguageConfigRegistry()
