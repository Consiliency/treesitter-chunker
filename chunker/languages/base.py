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


# Backward compatibility - PluginConfig from Phase 1.2
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

    def should_chunk_node(self, node_type: str, parent_type: str | None = None) -> bool:
        """Determine if a node should be treated as a chunk.

        Args:
            node_type: The type of the current node
            parent_type: The type of the parent node (if any)

        Returns:
            True if the node should be a chunk, False otherwise
        """
        # First check if it's in the ignore list
        if node_type in self.ignore_types:
            return False

        # Check basic chunk types
        if node_type in self.chunk_types:
            return True

        # Check advanced rules
        for rule in self.chunk_rules:
            if node_type in rule.node_types:
                return True

        return False

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
        # Ensure chunk_types doesn't overlap with ignore_types
        overlap = self.chunk_types & self.ignore_types
        if overlap:
            raise ValueError(
                f"Configuration error: Node types cannot be both chunk types "
                f"and ignore types: {overlap}",
            )

    def __repr__(self) -> str:
        """Return a string representation of the configuration."""
        return (
            f"{self.__class__.__name__}("
            f"language_id={self.language_id!r}, "
            f"chunk_types={len(self.chunk_types)}, "
            f"ignore_types={len(self.ignore_types)}, "
            f"rules={len(self.chunk_rules)})"
        )


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
        rules = []
        for parent in self._parent_configs:
            rules.extend(parent.chunk_rules)
        rules.extend(self._chunk_rules)
        # Sort by priority
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

    # Check language_id
    if not config.language_id:
        errors.append("Language ID cannot be empty")

    # Check for empty chunk_types
    if not config.chunk_types:
        errors.append("Configuration must define at least one chunk type")

    # Check for invalid characters in node types
    for node_type in config.chunk_types | config.ignore_types:
        if not node_type or not isinstance(node_type, str):
            errors.append(f"Invalid node type: {node_type!r}")
        elif " " in node_type:
            errors.append(f"Node type cannot contain spaces: {node_type!r}")

    # Check for overlapping chunk and ignore types
    overlap = config.chunk_types & config.ignore_types
    if overlap:
        errors.append(f"Node types cannot be both chunk and ignore types: {overlap}")

    # Validate chunk rules
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

    def __init__(self):
        """Initialize the registry."""
        self._configs: dict[str, LanguageConfig] = {}
        self._aliases: dict[str, str] = {}

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
        # Validate the configuration
        errors = validate_language_config(config)
        if errors:
            raise ValueError(
                f"Invalid configuration for {config.language_id}: " + "; ".join(errors),
            )

        # Check if already registered
        if config.language_id in self._configs:
            raise ValueError(f"Language {config.language_id} is already registered")

        # Register the configuration
        self._configs[config.language_id] = config
        logger.info(f"Registered language configuration: {config.language_id}")

        # Register aliases
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
        # Check if it's an alias
        if language_id in self._aliases:
            language_id = self._aliases[language_id]

        return self._configs.get(language_id)

    def list_languages(self) -> list[str]:
        """List all registered language IDs."""
        return sorted(self._configs.keys())

    def clear(self) -> None:
        """Clear all registered configurations."""
        self._configs.clear()
        self._aliases.clear()


# Global registry instance
language_config_registry = LanguageConfigRegistry()
