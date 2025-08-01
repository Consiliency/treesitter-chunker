"""Plugin system base classes for tree-sitter-chunker.

This module provides the plugin interface that wraps around the language
configuration system from Phase 2.1.
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chunker.types import CodeChunk

if TYPE_CHECKING:
    from pathlib import Path

    from tree_sitter import Node, Parser

    from .base import LanguageConfig

logger = logging.getLogger(__name__)


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


class LanguagePlugin(ABC):
    """Abstract base class for language-specific chunking plugins.

    This wraps around the LanguageConfig system to provide backward
    compatibility with the plugin architecture.
    """

    # Plugin API version - increment when breaking changes are made
    PLUGIN_API_VERSION = "1.0"

    def __init__(self, config: PluginConfig | None = None):
        self.config = config or PluginConfig()
        self._parser: Parser | None = None
        self._language_config: LanguageConfig | None = None
        self._validate_plugin()

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language identifier (e.g., 'python', 'rust')."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return set of file extensions this plugin handles (e.g., {'.py', '.pyi'})."""

    @property
    def chunk_node_types(self) -> set[str]:
        """Return set of tree-sitter node types to chunk."""
        if self.config.chunk_types:
            return self.config.chunk_types
        return self.default_chunk_types

    @property
    @abstractmethod
    def default_chunk_types(self) -> set[str]:
        """Return default set of node types to chunk for this language."""

    @property
    def plugin_version(self) -> str:
        """Return the plugin version. Override in subclasses."""
        return "1.0.0"

    @property
    def minimum_api_version(self) -> str:
        """Return minimum required API version. Override if needed."""
        return "1.0"

    @property
    def plugin_metadata(self) -> dict[str, Any]:
        """Return plugin metadata. Override to add custom metadata."""
        return {
            "name": self.__class__.__name__,
            "language": self.language_name,
            "version": self.plugin_version,
            "api_version": self.minimum_api_version,
            "extensions": list(self.supported_extensions),
            "chunk_types": list(self.default_chunk_types),
        }

    def set_parser(self, parser: Parser) -> None:
        """Set the tree-sitter parser for this plugin."""
        self._parser = parser

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk | None:
        """
        Process a single node into a chunk.

        Args:
            node: Tree-sitter node to process
            source: Source code bytes
            file_path: Path to the source file
            parent_context: Context from parent node (e.g., class name for methods)

        Returns:
            CodeChunk if node should be chunked, None otherwise
        """
        if node.type not in self.chunk_node_types:
            return None

        chunk = self.create_chunk(node, source, file_path, parent_context)

        # Apply size filters
        if chunk and self.should_include_chunk(chunk):
            return chunk

        return None

    def create_chunk(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> CodeChunk:
        """Create a CodeChunk from a node. Can be overridden for custom behavior."""
        content = source[node.start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )

        return CodeChunk(
            language=self.language_name,
            file_path=file_path,
            node_type=node.type,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
            parent_context=parent_context or "",
            content=content,
        )

    def should_include_chunk(self, chunk: CodeChunk) -> bool:
        """Apply filters to determine if chunk should be included."""
        # Filter by size
        lines = chunk.end_line - chunk.start_line + 1

        if lines < self.config.min_chunk_size:
            return False

        return not (self.config.max_chunk_size and lines > self.config.max_chunk_size)

    def walk_tree(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ) -> list[CodeChunk]:
        """
        Recursively walk the tree and extract chunks.

        Args:
            node: Current tree-sitter node
            source: Source code bytes
            file_path: Path to the source file
            parent_context: Context from parent node

        Returns:
            List of CodeChunk objects
        """
        chunks: list[CodeChunk] = []

        # Process current node
        chunk = self.process_node(node, source, file_path, parent_context)
        if chunk:
            chunks.append(chunk)
            # Update parent context for children
            parent_context = self.get_context_for_children(node, chunk)

        # Process children
        for child in node.children:
            chunks.extend(
                self.walk_tree(child, source, file_path, parent_context),
            )

        return chunks

    def get_context_for_children(self, _node: Node, chunk: CodeChunk) -> str:
        """
        Get context string to pass to children nodes.
        Can be overridden for language-specific context building.
        """
        return chunk.node_type

    def chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Parse a file and return chunks."""
        if not self._parser:
            raise RuntimeError(f"Parser not set for {self.language_name} plugin")

        source = file_path.read_bytes()
        tree = self._parser.parse(source)

        return self.walk_tree(
            tree.root_node,
            source,
            str(file_path),
        )

    @abstractmethod
    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """
        Extract a human-readable name from a node (e.g., function name).
        Used for better context building.
        """

    def _validate_plugin(self) -> None:
        """Validate plugin compatibility and requirements."""
        # Check API version compatibility
        if not self._is_api_compatible():
            raise RuntimeError(
                f"Plugin {self.__class__.__name__} requires API version "
                f"{self.minimum_api_version} but system provides {self.PLUGIN_API_VERSION}",
            )

        # Validate required properties
        try:
            _ = self.language_name
            _ = self.supported_extensions
            _ = self.default_chunk_types
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(
                f"Plugin {self.__class__.__name__} failed validation: {e}",
            ) from e

        logger.debug(
            f"Plugin {self.__class__.__name__} v{self.plugin_version} "
            f"validated successfully for language '{self.language_name}'",
        )

    def _is_api_compatible(self) -> bool:
        """Check if plugin is compatible with current API version."""

        def parse_version(version: str) -> tuple[int, int]:
            """Parse version string to tuple of (major, minor)."""
            parts = version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return (major, minor)

        current_version = parse_version(self.PLUGIN_API_VERSION)
        required_version = parse_version(self.minimum_api_version)

        # Major version must match, minor version must be >= required
        return (
            current_version[0] == required_version[0]
            and current_version[1] >= required_version[1]
        )
