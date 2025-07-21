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
]

from .visualization.ast_visualizer import ASTVisualizer, render_ast_graph, print_ast_tree
from .visualization.chunk_visualizer import highlight_chunk_boundaries
from .interactive.query_debugger import QueryDebugger, debug_query
from .interactive.chunk_debugger import ChunkDebugger
from .interactive.node_explorer import NodeExplorer, explore_ast
from .interactive.repl import start_repl