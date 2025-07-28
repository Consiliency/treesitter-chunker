"""
Tree-sitter Chunker Debug Module - Tools for debugging and visualization.
"""

__all__ = [
    # Core visualizer
    "ASTVisualizer",
    "ChunkComparisonImpl",
    "ChunkDebugger",
    # Contract implementations
    "DebugVisualizationImpl",
    "NodeExplorer",
    # Debuggers
    "QueryDebugger",
    "debug_query",
    "explore_ast",
    "highlight_chunk_boundaries",
    "print_ast_tree",
    # Visualization utilities
    "render_ast_graph",
    # Interactive tools
    "start_repl",
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
