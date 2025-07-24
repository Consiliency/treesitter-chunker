"""
AST Visualizer for Tree-sitter parse trees.
"""

from typing import Any

try:
    import graphviz

    HAS_GRAPHVIZ = True
except ImportError:
    HAS_GRAPHVIZ = False

from rich.console import Console
from rich.tree import Tree
from tree_sitter import Node

from ...parser import get_parser
from ...types import CodeChunk


class ASTVisualizer:
    """Visualizes Tree-sitter ASTs with various output formats."""

    def __init__(self, language: str):
        """Initialize visualizer for a specific language."""
        self.language = language
        self.parser = get_parser(language)
        self.console = Console()

    def visualize_file(
        self,
        file_path: str,
        output_format: str = "tree",
        chunks: list[CodeChunk] | None = None,
        max_depth: int | None = None,
        show_positions: bool = True,
        highlight_nodes: set[str] | None = None,
    ) -> str | None:
        """
        Visualize AST for a file.

        Args:
            file_path: Path to source file
            output_format: One of "tree", "graph", "json"
            chunks: Optional list of chunks to highlight
            max_depth: Maximum depth to display
            show_positions: Whether to show node positions
            highlight_nodes: Set of node types to highlight

        Returns:
            String representation for graph format, None for console output
        """
        with open(file_path, "rb") as f:
            content = f.read()

        tree = self.parser.parse(content)

        if output_format == "tree":
            self._print_tree(
                tree.root_node,
                content,
                chunks=chunks,
                max_depth=max_depth,
                show_positions=show_positions,
                highlight_nodes=highlight_nodes,
            )
            return None
        if output_format == "graph":
            return self._render_graph(
                tree.root_node,
                content,
                chunks=chunks,
                max_depth=max_depth,
                highlight_nodes=highlight_nodes,
            )
        if output_format == "json":
            return self._to_json(
                tree.root_node,
                content,
                chunks=chunks,
                max_depth=max_depth,
            )
        raise ValueError(f"Unknown output format: {output_format}")

    def _print_tree(
        self,
        node: Node,
        content: bytes,
        chunks: list[CodeChunk] | None = None,
        max_depth: int | None = None,
        show_positions: bool = True,
        highlight_nodes: set[str] | None = None,
        _depth: int = 0,
        _rich_tree: Tree | None = None,
    ) -> None:
        """Print AST as a rich tree to console."""
        if _rich_tree is None:
            _rich_tree = Tree(
                self._format_node(
                    node,
                    content,
                    show_positions,
                    chunks,
                    highlight_nodes,
                ),
            )

        if max_depth is not None and _depth >= max_depth:
            _rich_tree.add("...")
            return

        for child in node.children:
            is_chunk_boundary = self._is_chunk_boundary(child, chunks)
            child_label = self._format_node(
                child,
                content,
                show_positions,
                chunks,
                highlight_nodes,
            )

            if is_chunk_boundary:
                child_label = f"[bold red]→[/bold red] {child_label}"

            child_tree = _rich_tree.add(child_label)

            if child.child_count > 0:
                self._print_tree(
                    child,
                    content,
                    chunks,
                    max_depth,
                    show_positions,
                    highlight_nodes,
                    _depth + 1,
                    child_tree,
                )

        if _depth == 0:
            self.console.print(_rich_tree)

    def _format_node(
        self,
        node: Node,
        content: bytes,
        show_positions: bool,
        chunks: list[CodeChunk] | None,
        highlight_nodes: set[str] | None,
    ) -> str:
        """Format a node for display."""
        parts = []

        # Node type
        node_type = node.type
        if highlight_nodes and node_type in highlight_nodes:
            parts.append(f"[bold yellow]{node_type}[/bold yellow]")
        else:
            parts.append(f"[green]{node_type}[/green]")

        # Field name if available (field_name is accessed through parent)
        # Skip field name for now as it requires parent tracking

        # Position info
        if show_positions:
            start = node.start_point
            end = node.end_point
            parts.append(f"[dim]<{start[0]}:{start[1]}-{end[0]}:{end[1]}>[/dim]")

        # Node text preview (for leaf nodes)
        if node.child_count == 0:
            text = content[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            if len(text) > 50:
                text = text[:47] + "..."
            # Escape special characters
            text = repr(text)[1:-1]
            parts.append(f'[cyan]"{text}"[/cyan]')

        # Chunk indicator
        if chunks and self._node_in_chunk(node, chunks):
            parts.append("[red]●[/red]")

        return " ".join(parts)

    def _is_chunk_boundary(self, node: Node, chunks: list[CodeChunk] | None) -> bool:
        """Check if node is at a chunk boundary."""
        if not chunks:
            return False

        for chunk in chunks:
            if node.start_byte == chunk.byte_start and node.end_byte == chunk.byte_end:
                return True
        return False

    def _node_in_chunk(self, node: Node, chunks: list[CodeChunk]) -> bool:
        """Check if node is within any chunk."""
        for chunk in chunks:
            if node.start_byte >= chunk.byte_start and node.end_byte <= chunk.byte_end:
                return True
        return False

    def _render_graph(
        self,
        node: Node,
        content: bytes,
        chunks: list[CodeChunk] | None = None,
        max_depth: int | None = None,
        highlight_nodes: set[str] | None = None,
    ) -> str:
        """Render AST as a graphviz graph."""
        if not HAS_GRAPHVIZ:
            raise ImportError("graphviz package required for graph output")

        dot = graphviz.Digraph(comment="AST", format="svg")
        dot.attr(rankdir="TB")

        self._add_graph_node(
            dot,
            node,
            content,
            chunks,
            max_depth,
            highlight_nodes,
            0,
        )

        return dot.source

    def _add_graph_node(
        self,
        dot: Any,  # graphviz.Digraph when available
        node: Node,
        content: bytes,
        chunks: list[CodeChunk] | None,
        max_depth: int | None,
        highlight_nodes: set[str] | None,
        depth: int,
        parent_id: str | None = None,
    ) -> str:
        """Add a node to the graphviz graph."""
        node_id = f"{id(node)}"

        # Determine node style
        style_attrs = {}
        if chunks and self._is_chunk_boundary(node, chunks):
            style_attrs.update(
                {
                    "style": "filled",
                    "fillcolor": "lightcoral",
                    "penwidth": "2",
                },
            )
        elif chunks and self._node_in_chunk(node, chunks):
            style_attrs.update(
                {
                    "style": "filled",
                    "fillcolor": "lightblue",
                },
            )
        elif highlight_nodes and node.type in highlight_nodes:
            style_attrs.update(
                {
                    "style": "filled",
                    "fillcolor": "lightyellow",
                },
            )

        # Create label
        label_parts = [node.type]
        # Skip field name for now
        if node.child_count == 0:
            text = content[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            if len(text) > 30:
                text = text[:27] + "..."
            label_parts.append(f'\\n"{text}"')

        dot.node(node_id, "\\n".join(label_parts), **style_attrs)

        if parent_id:
            dot.edge(parent_id, node_id)

        if max_depth is None or depth < max_depth:
            for child in node.children:
                self._add_graph_node(
                    dot,
                    child,
                    content,
                    chunks,
                    max_depth,
                    highlight_nodes,
                    depth + 1,
                    node_id,
                )

        return node_id

    def _to_json(
        self,
        node: Node,
        content: bytes,
        chunks: list[CodeChunk] | None = None,
        max_depth: int | None = None,
        _depth: int = 0,
    ) -> str:
        """Convert AST to JSON representation."""
        import json

        def node_to_dict(n: Node, d: int = 0) -> dict[str, Any]:
            result = {
                "type": n.type,
                "start_byte": n.start_byte,
                "end_byte": n.end_byte,
                "start_point": list(n.start_point),
                "end_point": list(n.end_point),
            }

            # Skip field name for now

            if n.child_count == 0:
                result["text"] = content[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )

            if chunks:
                result["in_chunk"] = self._node_in_chunk(n, chunks)
                result["is_chunk_boundary"] = self._is_chunk_boundary(n, chunks)

            if max_depth is None or d < max_depth:
                result["children"] = [node_to_dict(c, d + 1) for c in n.children]

            return result

        return json.dumps(node_to_dict(node), indent=2)


def render_ast_graph(
    file_path: str,
    language: str,
    output_path: str | None = None,
    chunks: list[CodeChunk] | None = None,
    format: str = "svg",
    highlight_nodes: set[str] | None = None,
) -> str | None:
    """
    Render AST as a graph file.

    Args:
        file_path: Source file path
        language: Programming language
        output_path: Where to save the graph (optional)
        chunks: Chunks to highlight
        format: Output format (svg, png, pdf, etc.)
        highlight_nodes: Node types to highlight

    Returns:
        Graph source if no output_path, None otherwise
    """
    visualizer = ASTVisualizer(language)
    graph_source = visualizer.visualize_file(
        file_path,
        output_format="graph",
        chunks=chunks,
        highlight_nodes=highlight_nodes,
    )

    if output_path and HAS_GRAPHVIZ:
        dot = graphviz.Source(graph_source)
        dot.format = format
        dot.render(output_path, cleanup=True)
        return None

    return graph_source


def print_ast_tree(
    file_path: str,
    language: str,
    chunks: list[CodeChunk] | None = None,
    max_depth: int | None = None,
    show_positions: bool = True,
    highlight_nodes: set[str] | None = None,
) -> None:
    """
    Print AST as a tree to console.

    Args:
        file_path: Source file path
        language: Programming language
        chunks: Chunks to highlight
        max_depth: Maximum depth to display
        show_positions: Whether to show node positions
        highlight_nodes: Node types to highlight
    """
    visualizer = ASTVisualizer(language)
    visualizer.visualize_file(
        file_path,
        output_format="tree",
        chunks=chunks,
        max_depth=max_depth,
        show_positions=show_positions,
        highlight_nodes=highlight_nodes,
    )
