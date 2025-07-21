"""
Chunk boundary visualization for Tree-sitter chunker.
"""

from typing import List, Optional, Tuple
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from pygments.lexers import get_lexer_by_name

from ...types import CodeChunk
from ...chunker import chunk_file


def highlight_chunk_boundaries(
    file_path: str,
    language: str,
    chunks: Optional[List[CodeChunk]] = None,
    show_stats: bool = True,
    show_side_by_side: bool = False
) -> None:
    """
    Highlight chunk boundaries in source code.
    
    Args:
        file_path: Path to source file
        language: Programming language
        chunks: Optional pre-computed chunks
        show_stats: Whether to show chunk statistics
        show_side_by_side: Show original and chunked side-by-side
    """
    console = Console()
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.splitlines()
    
    # Get chunks if not provided
    if chunks is None:
        chunks = chunk_file(file_path, language)
    
    # Sort chunks by start position
    chunks.sort(key=lambda c: c.byte_start)
    
    if show_stats:
        _print_chunk_stats(chunks, console)
    
    if show_side_by_side:
        _show_side_by_side(content, chunks, language, console)
    else:
        _show_inline_boundaries(lines, chunks, language, console, file_path)


def _print_chunk_stats(chunks: List[CodeChunk], console: Console) -> None:
    """Print statistics about chunks."""
    table = Table(title="Chunk Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    total_chunks = len(chunks)
    total_bytes = sum(c.byte_end - c.byte_start for c in chunks)
    avg_size = total_bytes / total_chunks if total_chunks > 0 else 0
    
    table.add_row("Total Chunks", str(total_chunks))
    table.add_row("Total Bytes", f"{total_bytes:,}")
    table.add_row("Average Size", f"{avg_size:.1f} bytes")
    
    # Size distribution
    if chunks:
        sizes = [c.byte_end - c.byte_start for c in chunks]
        table.add_row("Min Size", f"{min(sizes):,} bytes")
        table.add_row("Max Size", f"{max(sizes):,} bytes")
    
    # Type distribution
    type_counts = {}
    for chunk in chunks:
        chunk_type = chunk.node_type
        type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
    
    type_table = Table(title="Chunk Types")
    type_table.add_column("Type", style="cyan")
    type_table.add_column("Count", style="green")
    
    for chunk_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        type_table.add_row(chunk_type, str(count))
    
    console.print(table)
    console.print()
    console.print(type_table)
    console.print()


def _show_inline_boundaries(
    lines: List[str],
    chunks: List[CodeChunk],
    language: str,
    console: Console,
    file_path: str = "untitled"
) -> None:
    """Show chunk boundaries inline with syntax highlighting."""
    # Create a mapping of line numbers to chunk info
    line_to_chunks = {}
    
    for i, chunk in enumerate(chunks):
        start_line = chunk.start_line - 1  # Convert to 0-based
        end_line = chunk.end_line - 1
        
        # Mark chunk start
        if start_line not in line_to_chunks:
            line_to_chunks[start_line] = []
        line_to_chunks[start_line].append(('start', i, chunk))
        
        # Mark chunk end
        if end_line not in line_to_chunks:
            line_to_chunks[end_line] = []
        line_to_chunks[end_line].append(('end', i, chunk))
    
    # Build annotated source
    annotated_lines = []
    
    for line_no, line in enumerate(lines):
        # Check for chunk boundaries
        if line_no in line_to_chunks:
            for boundary_type, chunk_idx, chunk in line_to_chunks[line_no]:
                node_type = chunk.node_type
                
                if boundary_type == 'start':
                    annotated_lines.append(
                        f"[bold green]// ┌─── CHUNK {chunk_idx + 1} START: {node_type} ───[/bold green]"
                    )
                else:
                    annotated_lines.append(
                        f"[bold red]// └─── CHUNK {chunk_idx + 1} END ───[/bold red]"
                    )
        
        annotated_lines.append(line)
    
    # Create syntax-highlighted view
    syntax = Syntax(
        '\n'.join(annotated_lines),
        language,
        theme="monokai",
        line_numbers=True
    )
    
    console.print(Panel(syntax, title=f"Chunked: {Path(file_path).name}"))


def _show_side_by_side(
    content: str,
    chunks: List[CodeChunk],
    language: str,
    console: Console
) -> None:
    """Show original and chunked code side by side."""
    # Original code panel
    original_syntax = Syntax(
        content,
        language,
        theme="monokai",
        line_numbers=True
    )
    original_panel = Panel(original_syntax, title="Original")
    
    # Chunked code panels
    chunk_panels = []
    for i, chunk in enumerate(chunks):
        chunk_content = chunk.content
        node_type = chunk.node_type 
        
        chunk_syntax = Syntax(
            chunk_content,
            language,
            theme="monokai",
            line_numbers=False
        )
        
        chunk_panel = Panel(
            chunk_syntax,
            title=f"Chunk {i + 1}: {node_type}",
            subtitle=f"Lines {chunk.start_point[0] + 1}-{chunk.end_point[0] + 1}"
        )
        chunk_panels.append(chunk_panel)
    
    # Display side by side
    console.print(Columns([original_panel] + chunk_panels[:2]))
    
    # Display remaining chunks
    for i in range(2, len(chunk_panels), 2):
        remaining = chunk_panels[i:i+2]
        if remaining:
            console.print()
            console.print(Columns(remaining))