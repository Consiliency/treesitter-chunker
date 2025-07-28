"""Stub implementations of interfaces for testing.

These are minimal implementations that raise NotImplementedError
for all methods. Worktrees can import these for testing their
code before the actual implementations are available.
"""

import io
from pathlib import Path
from re import Pattern
from typing import Any

from tree_sitter import Node

from chunker.types import CodeChunk

from .base import ASTProcessor, ChunkingStrategy
from .context import ContextExtractor, ContextItem
from .debug import ASTVisualizer
from .export import ChunkRelationship, ExportFormat, StructuredExporter
from .fallback import FallbackChunker
from .grammar import GrammarManager
from .performance import CacheManager
from .query import Query, QueryEngine, QueryMatch

# Base stubs


class ChunkingStrategyStub(ChunkingStrategy):
    """Stub implementation of ChunkingStrategy."""

    def can_handle(self, file_path: str, language: str) -> bool:
        raise NotImplementedError("ChunkingStrategyStub.can_handle not implemented")

    def chunk(
        self,
        ast: Node,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        raise NotImplementedError("ChunkingStrategyStub.chunk not implemented")

    def configure(self, config: dict[str, Any]) -> None:
        raise NotImplementedError("ChunkingStrategyStub.configure not implemented")


class ASTProcessorStub(ASTProcessor):
    """Stub implementation of ASTProcessor."""

    def process_node(self, node: Node, context: dict[str, Any]) -> Any:
        raise NotImplementedError("ASTProcessorStub.process_node not implemented")

    def should_process_children(self, node: Node, context: dict[str, Any]) -> bool:
        raise NotImplementedError(
            "ASTProcessorStub.should_process_children not implemented",
        )


# Query stubs


class QueryStub(Query):
    """Stub implementation of Query."""

    def pattern_count(self) -> int:
        raise NotImplementedError("QueryStub.pattern_count not implemented")

    def capture_names(self) -> list[str]:
        raise NotImplementedError("QueryStub.capture_names not implemented")

    def disable_pattern(self, pattern_index: int) -> None:
        raise NotImplementedError("QueryStub.disable_pattern not implemented")

    def is_pattern_enabled(self, pattern_index: int) -> bool:
        raise NotImplementedError("QueryStub.is_pattern_enabled not implemented")


class QueryEngineStub(QueryEngine):
    """Stub implementation of QueryEngine."""

    def parse_query(self, query_string: str, language: str) -> Query:
        raise NotImplementedError("QueryEngineStub.parse_query not implemented")

    def execute_query(self, ast: Node, query: Query) -> list[QueryMatch]:
        raise NotImplementedError("QueryEngineStub.execute_query not implemented")

    def validate_query(
        self,
        query_string: str,
        language: str,
    ) -> tuple[bool, str | None]:
        raise NotImplementedError("QueryEngineStub.validate_query not implemented")


# Context stubs


class ContextExtractorStub(ContextExtractor):
    """Stub implementation of ContextExtractor."""

    def extract_imports(self, ast: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_imports not implemented",
        )

    def extract_type_definitions(self, ast: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_type_definitions not implemented",
        )

    def extract_dependencies(
        self,
        node: Node,
        ast: Node,
        source: bytes,
    ) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_dependencies not implemented",
        )

    def extract_parent_context(
        self,
        node: Node,
        ast: Node,
        source: bytes,
    ) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_parent_context not implemented",
        )

    def find_decorators(self, node: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.find_decorators not implemented",
        )

    def build_context_prefix(
        self,
        context_items: list[ContextItem],
        max_size: int | None = None,
    ) -> str:
        raise NotImplementedError(
            "ContextExtractorStub.build_context_prefix not implemented",
        )

    def process_node(self, node: Node, context: dict[str, Any]) -> Any:
        raise NotImplementedError("ContextExtractorStub.process_node not implemented")

    def should_process_children(self, node: Node, context: dict[str, Any]) -> bool:
        raise NotImplementedError(
            "ContextExtractorStub.should_process_children not implemented",
        )


# Performance stubs


class CacheManagerStub(CacheManager):
    """Stub implementation of CacheManager."""

    def get(self, key: str) -> Any | None:
        raise NotImplementedError("CacheManagerStub.get not implemented")

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        raise NotImplementedError("CacheManagerStub.put not implemented")

    def invalidate(self, key: str) -> bool:
        raise NotImplementedError("CacheManagerStub.invalidate not implemented")

    def invalidate_pattern(self, pattern: str) -> int:
        raise NotImplementedError("CacheManagerStub.invalidate_pattern not implemented")

    def clear(self) -> None:
        raise NotImplementedError("CacheManagerStub.clear not implemented")

    def size(self) -> int:
        raise NotImplementedError("CacheManagerStub.size not implemented")

    def memory_usage(self) -> int:
        raise NotImplementedError("CacheManagerStub.memory_usage not implemented")

    def evict_expired(self) -> int:
        raise NotImplementedError("CacheManagerStub.evict_expired not implemented")

    def get_stats(self) -> dict[str, Any]:
        raise NotImplementedError("CacheManagerStub.get_stats not implemented")


# Export stubs


class StructuredExporterStub(StructuredExporter):
    """Stub implementation of StructuredExporter."""

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: Any | None = None,
    ) -> None:
        raise NotImplementedError("StructuredExporterStub.export not implemented")

    def export_streaming(
        self,
        chunk_iterator: Any,
        relationship_iterator: Any,
        output: Path | io.IOBase,
    ) -> None:
        raise NotImplementedError(
            "StructuredExporterStub.export_streaming not implemented",
        )

    def supports_format(self, format: ExportFormat) -> bool:
        raise NotImplementedError(
            "StructuredExporterStub.supports_format not implemented",
        )

    def get_schema(self) -> dict[str, Any]:
        raise NotImplementedError("StructuredExporterStub.get_schema not implemented")


# Grammar stubs


class GrammarManagerStub(GrammarManager):
    """Stub implementation of GrammarManager."""

    def add_grammar(
        self,
        name: str,
        repository_url: str,
        commit_hash: str | None = None,
    ) -> Any:
        raise NotImplementedError("GrammarManagerStub.add_grammar not implemented")

    def fetch_grammar(self, name: str) -> bool:
        raise NotImplementedError("GrammarManagerStub.fetch_grammar not implemented")

    def build_grammar(self, name: str) -> bool:
        raise NotImplementedError("GrammarManagerStub.build_grammar not implemented")

    def get_grammar_info(self, name: str) -> Any | None:
        raise NotImplementedError("GrammarManagerStub.get_grammar_info not implemented")

    def list_grammars(self, status: Any | None = None) -> list[Any]:
        raise NotImplementedError("GrammarManagerStub.list_grammars not implemented")

    def update_grammar(self, name: str) -> bool:
        raise NotImplementedError("GrammarManagerStub.update_grammar not implemented")

    def remove_grammar(self, name: str) -> bool:
        raise NotImplementedError("GrammarManagerStub.remove_grammar not implemented")

    def get_node_types(self, language: str) -> list[Any]:
        raise NotImplementedError("GrammarManagerStub.get_node_types not implemented")

    def validate_grammar(self, name: str) -> tuple[bool, str | None]:
        raise NotImplementedError("GrammarManagerStub.validate_grammar not implemented")


# Fallback stubs


class FallbackChunkerStub(FallbackChunker):
    """Stub implementation of FallbackChunker."""

    def can_handle(self, file_path: str, language: str) -> bool:
        raise NotImplementedError("FallbackChunkerStub.can_handle not implemented")

    def chunk(
        self,
        ast: Node,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        raise NotImplementedError("FallbackChunkerStub.chunk not implemented")

    def configure(self, config: dict[str, Any]) -> None:
        raise NotImplementedError("FallbackChunkerStub.configure not implemented")

    def set_fallback_reason(self, reason: Any) -> None:
        raise NotImplementedError(
            "FallbackChunkerStub.set_fallback_reason not implemented",
        )

    def chunk_by_lines(
        self,
        content: str,
        lines_per_chunk: int,
        overlap_lines: int = 0,
    ) -> list[CodeChunk]:
        raise NotImplementedError("FallbackChunkerStub.chunk_by_lines not implemented")

    def chunk_by_delimiter(
        self,
        content: str,
        delimiter: str,
        include_delimiter: bool = True,
    ) -> list[CodeChunk]:
        raise NotImplementedError(
            "FallbackChunkerStub.chunk_by_delimiter not implemented",
        )

    def chunk_by_pattern(
        self,
        content: str,
        pattern: Pattern,
        include_match: bool = True,
    ) -> list[CodeChunk]:
        raise NotImplementedError(
            "FallbackChunkerStub.chunk_by_pattern not implemented",
        )

    def emit_warning(self) -> str:
        raise NotImplementedError("FallbackChunkerStub.emit_warning not implemented")


# Debug stubs


class ASTVisualizerStub(ASTVisualizer):
    """Stub implementation of ASTVisualizer."""

    def visualize(self, node: Node, source: bytes, format: Any = None) -> str:
        raise NotImplementedError("ASTVisualizerStub.visualize not implemented")

    def visualize_with_chunks(
        self,
        node: Node,
        source: bytes,
        chunks: list[CodeChunk],
        format: Any = None,
    ) -> str:
        raise NotImplementedError(
            "ASTVisualizerStub.visualize_with_chunks not implemented",
        )

    def highlight_nodes(self, nodes: list[Node], style: Any) -> None:
        raise NotImplementedError("ASTVisualizerStub.highlight_nodes not implemented")

    def set_max_depth(self, depth: int) -> None:
        raise NotImplementedError("ASTVisualizerStub.set_max_depth not implemented")

    def set_node_filter(self, filter_func: Any) -> None:
        raise NotImplementedError("ASTVisualizerStub.set_node_filter not implemented")

    def export_interactive(self, output_path: str) -> None:
        raise NotImplementedError(
            "ASTVisualizerStub.export_interactive not implemented",
        )


# Export all stubs for easy import
__all__ = [
    "ASTProcessorStub",
    "ASTVisualizerStub",
    "CacheManagerStub",
    "ChunkingStrategyStub",
    "ContextExtractorStub",
    "FallbackChunkerStub",
    "GrammarManagerStub",
    "QueryEngineStub",
    "QueryStub",
    "StructuredExporterStub",
]
