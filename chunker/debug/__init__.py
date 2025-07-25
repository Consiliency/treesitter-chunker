"""
Tree-sitter Chunker Debug Module - Tools for debugging and visualization.
"""

__all__ = [
    # Core visualizer
    "ASTVisualizer",
    # Debuggers
    "QueryDebugger",
    "ChunkDebugger",
    "NodeExplorer",
    # Visualization utilities
    "render_ast_graph",
    "print_ast_tree",
    "highlight_chunk_boundaries",
    # Interactive tools
    "start_repl",
    "debug_query",
    "explore_ast",
    # Contract implementations
    "DebugVisualizationImpl",
    "ChunkComparisonImpl",
]

from .comparison import ChunkComparisonImpl
from .interactive.chunk_debugger import ChunkDebugger
from .interactive.node_explorer import NodeExplorer, explore_ast
from .interactive.query_debugger import QueryDebugger, debug_query
from .interactive.repl import start_repl
from .visualization.ast_visualizer import (
    ASTVisualizer,
    print_ast_tree,
    render_ast_graph,
)
from .visualization.chunk_visualizer import highlight_chunk_boundaries
from .visualization_impl import DebugVisualizationImpl
