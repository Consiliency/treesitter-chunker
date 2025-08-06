"""
Interactive debugger for analyzing chunking decisions.
"""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from tree_sitter import Node

from chunker.core import chunk_file
from chunker.parser import get_parser
from chunker.types import CodeChunk


class ChunkDebugger:
    """Debug and analyze chunking decisions."""

    def __init__(self, language: str):
        """Initialize chunk debugger."""
        self.language = language
        self.parser = get_parser(language)
        self.console = Console()

    def analyze_file(
        self,
        file_path: str,
        show_decisions: bool = True,
        show_overlap: bool = True,
        show_gaps: bool = True,
        max_chunk_size: int | None = None,
        min_chunk_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Analyze chunking for a file.

        Args:
            file_path: Path to analyze
            show_decisions: Show chunking decision tree
            show_overlap: Check for overlapping chunks
            show_gaps: Check for gaps in coverage
            max_chunk_size: Flag chunks exceeding this size
            min_chunk_size: Flag chunks below this size

        Returns:
            Analysis results dictionary
        """
        chunks = chunk_file(file_path, self.language)
        with Path(file_path).open("rb") as f:
            content = f.read()
        tree = self.parser.parse(content)
        analysis = {
            "total_chunks": len(chunks),
            "total_bytes": len(
                content,
            ),
            "chunked_bytes": sum(c.byte_end - c.byte_start for c in chunks),
            "coverage_percent": 0,
            "overlaps": [],
            "gaps": [],
            "size_issues": [],
            "decisions": [],
        }
        if len(content) > 0:
            analysis["coverage_percent"] = (
                analysis["chunked_bytes"] / analysis["total_bytes"] * 100
            )
        if show_overlap:
            analysis["overlaps"] = self._find_overlaps(chunks)
        if show_gaps:
            analysis["gaps"] = self._find_gaps(chunks, len(content))
        if max_chunk_size or min_chunk_size:
            analysis["size_issues"] = self._check_sizes(
                chunks,
                max_chunk_size,
                min_chunk_size,
            )
        if show_decisions:
            analysis["decisions"] = self._trace_decisions(
                tree.root_node,
                content,
                chunks,
            )
        self._display_analysis(analysis, file_path)
        return analysis

    @staticmethod
    def _find_overlaps(chunks: list[CodeChunk]) -> list[tuple[int, int]]:
        """Find overlapping chunks."""
        overlaps = []
        sorted_chunks = sorted(chunks, key=lambda c: c.byte_start)
        for i in range(len(sorted_chunks) - 1):
            curr = sorted_chunks[i]
            next_item = sorted_chunks[i + 1]
            if curr.byte_end > next_item.byte_start:
                overlaps.append((i, i + 1))
        return overlaps

    @staticmethod
    def _find_gaps(chunks: list[CodeChunk], total_bytes: int) -> list[tuple[int, int]]:
        """Find gaps in chunk coverage."""
        gaps = []
        sorted_chunks = sorted(chunks, key=lambda c: c.byte_start)
        if sorted_chunks and sorted_chunks[0].byte_start > 0:
            gaps.append((0, sorted_chunks[0].byte_start))
        for i in range(len(sorted_chunks) - 1):
            curr = sorted_chunks[i]
            next_item = sorted_chunks[i + 1]
            if curr.byte_end < next_item.byte_start:
                gaps.append((curr.byte_end, next_item.byte_start))
        if sorted_chunks and sorted_chunks[-1].byte_end < total_bytes:
            gaps.append((sorted_chunks[-1].byte_end, total_bytes))
        return gaps

    @staticmethod
    def _check_sizes(
        chunks: list[CodeChunk],
        max_size: int | None,
        min_size: int | None,
    ) -> list[tuple[int, str, int]]:
        """Check for size constraint violations."""
        issues = []
        for i, chunk in enumerate(chunks):
            size = chunk.byte_end - chunk.byte_start
            if max_size and size > max_size:
                issues.append((i, "exceeds_max", size))
            elif min_size and size < min_size:
                issues.append((i, "below_min", size))
        return issues

    @staticmethod
    def _trace_decisions(
        node: Node,
        _content: bytes,
        chunks: list[CodeChunk],
    ) -> list[dict[str, Any]]:
        """Trace chunking decisions for nodes."""
        decisions = []

        def analyze_node(n: Node, depth: int = 0) -> None:
            is_chunk = any(
                c.byte_start == n.start_byte and c.byte_end == n.end_byte
                for c in chunks
            )
            decision = {
                "node_type": n.type,
                "depth": depth,
                "byte_range": (n.start_byte, n.end_byte),
                "size": n.end_byte - n.start_byte,
                "is_chunk": is_chunk,
                "reasons": [],
            }
            if is_chunk:
                decision["reasons"].append("Matches chunking criteria")
                if n.type in {
                    "function_definition",
                    "class_definition",
                    "method_definition",
                    "function_declaration",
                }:
                    decision["reasons"].append(f"Node type '{n.type}' is chunkable")
            else:
                if n.end_byte - n.start_byte < 50:
                    decision["reasons"].append("Too small to chunk")
                if depth > 5:
                    decision["reasons"].append("Too deeply nested")
                if n.type not in {
                    "function_definition",
                    "class_definition",
                    "method_definition",
                    "function_declaration",
                }:
                    decision["reasons"].append(
                        f"Node type '{n.type}' not configured for chunking",
                    )
            decisions.append(decision)
            for child in n.children:
                analyze_node(child, depth + 1)

        analyze_node(node)
        return decisions

    def _display_analysis(
        self,
        analysis: dict[str, Any],
        file_path: str,
    ) -> None:
        """Display analysis results."""
        self.console.print(
            Panel(f"[bold]Chunk Analysis:[/bold] {Path(file_path).name}", expand=False),
        )
        summary = Table(title="Summary")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")
        summary.add_row("Total Chunks", str(analysis["total_chunks"]))
        summary.add_row("File Size", f"{analysis['total_bytes']:,} bytes")
        summary.add_row("Chunked Size", f"{analysis['chunked_bytes']:,} bytes")
        summary.add_row("Coverage", f"{analysis['coverage_percent']:.1f}%")
        self.console.print(summary)
        if analysis["overlaps"]:
            self.console.print("\n[red]Overlapping chunks found:[/red]")
            for i, j in analysis["overlaps"]:
                self.console.print(f"  • Chunks {i + 1} and {j + 1} overlap")
        if analysis["gaps"]:
            self.console.print("\n[yellow]Coverage gaps found:[/yellow]")
            gap_table = Table()
            gap_table.add_column("Start", style="cyan")
            gap_table.add_column("End", style="cyan")
            gap_table.add_column("Size", style="yellow")
            for start, end in analysis["gaps"]:
                gap_table.add_row(str(start), str(end), f"{end - start} bytes")
            self.console.print(gap_table)
        if analysis["size_issues"]:
            self.console.print(
                "\n[yellow]Size constraint violations:[/yellow]",
            )
            for chunk_idx, issue_type, size in analysis["size_issues"]:
                if issue_type == "exceeds_max":
                    self.console.print(
                        f"  • Chunk {chunk_idx + 1}: {size} bytes (exceeds maximum)",
                    )
                else:
                    self.console.print(
                        f"  • Chunk {chunk_idx + 1}: {size} bytes (below minimum)",
                    )
        if analysis["decisions"]:
            self._display_decision_tree(analysis["decisions"])

    def _display_decision_tree(self, decisions: list[dict[str, Any]]) -> None:
        """Display chunking decision tree."""
        self.console.print("\n[bold]Chunking Decisions:[/bold]")
        chunked = [d for d in decisions if d["is_chunk"]]
        not_chunked = [d for d in decisions if not d["is_chunk"]]
        if chunked:
            chunk_table = Table(title="Chunked Nodes")
            chunk_table.add_column("Type", style="green")
            chunk_table.add_column("Size", style="cyan")
            chunk_table.add_column("Reasons", style="white")
            for decision in chunked:
                chunk_table.add_row(
                    decision["node_type"],
                    f"{decision['size']} bytes",
                    "\n".join(decision["reasons"]),
                )
            self.console.print(chunk_table)
        if not_chunked:
            self.console.print(f"\n[dim]Not chunked: {len(not_chunked)} nodes[/dim]")
            examples = not_chunked[:5]
            for decision in examples:
                self.console.print(
                    f"  • {decision['node_type']} ({decision['size']} bytes): {', '.join(decision['reasons'])}",
                )
