# File: chunker/contracts/debug_stub.py
# Purpose: Concrete stub implementation for testing

from typing import Any, Union

from .debug_contract import ChunkComparisonContract, DebugVisualizationContract


class DebugVisualizationStub(DebugVisualizationContract):
    """Stub implementation that can be instantiated and tested"""

    def visualize_ast(
        self,
        file_path: str,
        language: str,
        output_format: str = "svg",
    ) -> Union[str, bytes]:
        """Stub that returns valid default values"""
        if output_format in ["svg", "dot", "json"]:
            return "Not implemented - Debug Tools team will implement"
        # png or other binary formats
        return b"Not implemented - Debug Tools team will implement"

    def inspect_chunk(
        self,
        file_path: str,
        chunk_id: str,
        include_context: bool = True,
    ) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Debug Tools",
            "content": "",
            "metadata": {},
            "boundaries": {"start": 0, "end": 0},
            "relationships": [],
            "tokens": 0,
            "complexity": 0,
            "ast_nodes": [],
        }

    def profile_chunking(self, file_path: str, language: str) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Debug Tools",
            "total_time": 0.0,
            "phases": {"parse": 0.0, "chunk": 0.0, "metadata": 0.0},
            "memory_usage": 0.0,
            "chunk_count": 0,
            "bottlenecks": [],
        }

    def debug_mode_chunking(
        self,
        file_path: str,
        language: str,
        breakpoints: list[str] | None = None,
    ) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Debug Tools",
            "trace": [],
            "decisions": [],
            "rules_applied": [],
        }


class ChunkComparisonStub(ChunkComparisonContract):
    """Stub implementation for chunk comparison"""

    def compare_strategies(
        self,
        file_path: str,
        language: str,
        strategies: list[str],
    ) -> dict[str, Any]:
        """Stub that returns valid default values"""
        return {
            "status": "not_implemented",
            "team": "Debug Tools",
            "comparisons": {},
            "metrics": {"chunk_counts": {}, "sizes": {}, "overlaps": {}},
            "visual_diff": None,
        }
