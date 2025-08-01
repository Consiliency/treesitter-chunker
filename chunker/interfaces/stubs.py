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


class ChunkingStrategyStub(ChunkingStrategy):
    """Stub implementation of ChunkingStrategy."""

    @staticmethod
    def can_handle(file_path: str, language: str) -> bool:
        raise NotImplementedError(
            "ChunkingStrategyStub.can_handle not implemented")

    @staticmethod
    def chunk(ast: Node, source: bytes, file_path: str, language: str) -> list[
        CodeChunk]:
        raise NotImplementedError("ChunkingStrategyStub.chunk not implemented")

    @staticmethod
    def configure(config: dict[str, Any]) -> None:
        raise NotImplementedError(
            "ChunkingStrategyStub.configure not implemented")


class ASTProcessorStub(ASTProcessor):
    """Stub implementation of ASTProcessor."""

    @staticmethod
    def process_node(node: Node, context: dict[str, Any]) -> Any:
        raise NotImplementedError(
            "ASTProcessorStub.process_node not implemented")

    @staticmethod
    def should_process_children(node: Node, context: dict[str, Any]) -> bool:
        raise NotImplementedError(
            "ASTProcessorStub.should_process_children not implemented")


class QueryStub(Query):
    """Stub implementation of Query."""

    @staticmethod
    def pattern_count() -> int:
        raise NotImplementedError("QueryStub.pattern_count not implemented")

    @staticmethod
    def capture_names() -> list[str]:
        raise NotImplementedError("QueryStub.capture_names not implemented")

    @staticmethod
    def disable_pattern(pattern_index: int) -> None:
        raise NotImplementedError("QueryStub.disable_pattern not implemented")

    @staticmethod
    def is_pattern_enabled(pattern_index: int) -> bool:
        raise NotImplementedError(
            "QueryStub.is_pattern_enabled not implemented")


class QueryEngineStub(QueryEngine):
    """Stub implementation of QueryEngine."""

    @staticmethod
    def parse_query(query_string: str, language: str) -> Query:
        raise NotImplementedError("QueryEngineStub.parse_query not implemented",
            )

    @staticmethod
    def execute_query(ast: Node, query: Query) -> list[QueryMatch]:
        raise NotImplementedError(
            "QueryEngineStub.execute_query not implemented")

    @staticmethod
    def validate_query(query_string: str, language: str) -> tuple[bool, str |
        None]:
        raise NotImplementedError(
            "QueryEngineStub.validate_query not implemented")


class ContextExtractorStub(ContextExtractor):
    """Stub implementation of ContextExtractor."""

    @staticmethod
    def extract_imports(ast: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_imports not implemented")

    @staticmethod
    def extract_type_definitions(ast: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_type_definitions not implemented")

    @staticmethod
    def extract_dependencies(node: Node, ast: Node, source: bytes) -> list[
        ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_dependencies not implemented")

    @staticmethod
    def extract_parent_context(node: Node, ast: Node, source: bytes) -> list[
        ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.extract_parent_context not implemented")

    @staticmethod
    def find_decorators(node: Node, source: bytes) -> list[ContextItem]:
        raise NotImplementedError(
            "ContextExtractorStub.find_decorators not implemented")

    @staticmethod
    def build_context_prefix(context_items: list[ContextItem], max_size: (
        int | None) = None) -> str:
        raise NotImplementedError(
            "ContextExtractorStub.build_context_prefix not implemented")

    @staticmethod
    def process_node(node: Node, context: dict[str, Any]) -> Any:
        raise NotImplementedError(
            "ContextExtractorStub.process_node not implemented")

    @staticmethod
    def should_process_children(node: Node, context: dict[str, Any]) -> bool:
        raise NotImplementedError(
            "ContextExtractorStub.should_process_children not implemented")


class CacheManagerStub(CacheManager):
    """Stub implementation of CacheManager."""

    @staticmethod
    def get(key: str) -> (Any | None):
        raise NotImplementedError("CacheManagerStub.get not implemented")

    @staticmethod
    def put(key: str, value: Any, ttl_seconds: (int | None) = None) -> None:
        raise NotImplementedError("CacheManagerStub.put not implemented")

    @staticmethod
    def invalidate(key: str) -> bool:
        raise NotImplementedError("CacheManagerStub.invalidate not implemented",
            )

    @staticmethod
    def invalidate_pattern(pattern: str) -> int:
        raise NotImplementedError(
            "CacheManagerStub.invalidate_pattern not implemented")

    @staticmethod
    def clear() -> None:
        raise NotImplementedError("CacheManagerStub.clear not implemented")

    @staticmethod
    def size() -> int:
        raise NotImplementedError("CacheManagerStub.size not implemented")

    @staticmethod
    def memory_usage() -> int:
        raise NotImplementedError(
            "CacheManagerStub.memory_usage not implemented")

    @staticmethod
    def evict_expired() -> int:
        raise NotImplementedError(
            "CacheManagerStub.evict_expired not implemented")

    @staticmethod
    def get_stats() -> dict[str, Any]:
        raise NotImplementedError("CacheManagerStub.get_stats not implemented")


class StructuredExporterStub(StructuredExporter):
    """Stub implementation of StructuredExporter."""

    @staticmethod
    def export(chunks: list[CodeChunk], relationships: list[
        ChunkRelationship], output: (Path | io.IOBase), metadata: (Any |
        None) = None) -> None:
        raise NotImplementedError(
            "StructuredExporterStub.export not implemented")

    @staticmethod
    def export_streaming(chunk_iterator: Any, relationship_iterator: Any,
        output: (Path | io.IOBase)) -> None:
        raise NotImplementedError(
            "StructuredExporterStub.export_streaming not implemented")

    @staticmethod
    def supports_format(fmt: ExportFormat) -> bool:
        raise NotImplementedError(
            "StructuredExporterStub.supports_format not implemented")

    @staticmethod
    def get_schema() -> dict[str, Any]:
        raise NotImplementedError(
            "StructuredExporterStub.get_schema not implemented")


class GrammarManagerStub(GrammarManager):
    """Stub implementation of GrammarManager."""

    @staticmethod
    def add_grammar(name: str, repository_url: str, commit_hash: (str |
        None) = None) -> Any:
        raise NotImplementedError(
            "GrammarManagerStub.add_grammar not implemented")

    @staticmethod
    def fetch_grammar(name: str) -> bool:
        raise NotImplementedError(
            "GrammarManagerStub.fetch_grammar not implemented")

    @staticmethod
    def build_grammar(name: str) -> bool:
        raise NotImplementedError(
            "GrammarManagerStub.build_grammar not implemented")

    @staticmethod
    def get_grammar_info(name: str) -> (Any | None):
        raise NotImplementedError(
            "GrammarManagerStub.get_grammar_info not implemented")

    @staticmethod
    def list_grammars(status: (Any | None) = None) -> list[Any]:
        raise NotImplementedError(
            "GrammarManagerStub.list_grammars not implemented")

    @staticmethod
    def update_grammar(name: str) -> bool:
        raise NotImplementedError(
            "GrammarManagerStub.update_grammar not implemented")

    @staticmethod
    def remove_grammar(name: str) -> bool:
        raise NotImplementedError(
            "GrammarManagerStub.remove_grammar not implemented")

    @staticmethod
    def get_node_types(language: str) -> list[Any]:
        raise NotImplementedError(
            "GrammarManagerStub.get_node_types not implemented")

    @staticmethod
    def validate_grammar(name: str) -> tuple[bool, str | None]:
        raise NotImplementedError(
            "GrammarManagerStub.validate_grammar not implemented")


class FallbackChunkerStub(FallbackChunker):
    """Stub implementation of FallbackChunker."""

    @staticmethod
    def can_handle(file_path: str, language: str) -> bool:
        raise NotImplementedError(
            "FallbackChunkerStub.can_handle not implemented")

    @staticmethod
    def chunk(ast: Node, source: bytes, file_path: str, language: str) -> list[
        CodeChunk]:
        raise NotImplementedError("FallbackChunkerStub.chunk not implemented")

    @staticmethod
    def configure(config: dict[str, Any]) -> None:
        raise NotImplementedError(
            "FallbackChunkerStub.configure not implemented")

    @staticmethod
    def set_fallback_reason(reason: Any) -> None:
        raise NotImplementedError(
            "FallbackChunkerStub.set_fallback_reason not implemented")

    @staticmethod
    def chunk_by_lines(content: str, lines_per_chunk: int, overlap_lines: int = 0,
        ) -> list[CodeChunk]:
        raise NotImplementedError(
            "FallbackChunkerStub.chunk_by_lines not implemented")

    @staticmethod
    def chunk_by_delimiter(content: str, delimiter: str, include_delimiter:
        bool = True) -> list[CodeChunk]:
        raise NotImplementedError(
            "FallbackChunkerStub.chunk_by_delimiter not implemented")

    @staticmethod
    def chunk_by_pattern(content: str, pattern: Pattern, include_match:
        bool = True) -> list[CodeChunk]:
        raise NotImplementedError(
            "FallbackChunkerStub.chunk_by_pattern not implemented")

    @staticmethod
    def emit_warning() -> str:
        raise NotImplementedError(
            "FallbackChunkerStub.emit_warning not implemented")


class ASTVisualizerStub(ASTVisualizer):
    """Stub implementation of ASTVisualizer."""

    @staticmethod
    def visualize(node: Node, source: bytes, fmt: Any = None) -> str:
        raise NotImplementedError("ASTVisualizerStub.visualize not implemented",
            )

    @staticmethod
    def visualize_with_chunks(node: Node, source: bytes, chunks: list[
        CodeChunk], fmt: Any = None) -> str:
        raise NotImplementedError(
            "ASTVisualizerStub.visualize_with_chunks not implemented")

    @staticmethod
    def highlight_nodes(nodes: list[Node], style: Any) -> None:
        raise NotImplementedError(
            "ASTVisualizerStub.highlight_nodes not implemented")

    @staticmethod
    def set_max_depth(depth: int) -> None:
        raise NotImplementedError(
            "ASTVisualizerStub.set_max_depth not implemented")

    @staticmethod
    def set_node_filter(filter_func: Any) -> None:
        raise NotImplementedError(
            "ASTVisualizerStub.set_node_filter not implemented")

    @staticmethod
    def export_interactive(output_path: str) -> None:
        raise NotImplementedError(
            "ASTVisualizerStub.export_interactive not implemented")


__all__ = ["ASTProcessorStub", "ASTVisualizerStub", "CacheManagerStub",
    "ChunkingStrategyStub", "ContextExtractorStub", "FallbackChunkerStub",
    "GrammarManagerStub", "QueryEngineStub", "QueryStub",
    "StructuredExporterStub"]
