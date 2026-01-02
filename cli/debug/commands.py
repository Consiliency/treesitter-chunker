"""
Debug CLI commands for Tree-sitter chunker.
"""

from pathlib import Path

import typer
from rich.console import Console

from chunker.core import chunk_file

# Import debug modules conditionally to handle missing graphviz
try:
    from chunker.debug import (
        ASTVisualizer,
        ChunkDebugger,
        NodeExplorer,
        QueryDebugger,
        highlight_chunk_boundaries,
        print_ast_tree,
        render_ast_graph,
    )
    from chunker.debug.interactive.repl import DebugREPL
    from chunker.parser import get_parser

    HAS_DEBUG_MODULES = True
except ImportError as e:
    if "graphviz" in str(e):
        # Create stub classes when graphviz is missing
        class ASTVisualizer:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "ASTVisualizer requires graphviz. Install with: pip install treesitter-chunker[viz]"
                )

        class ChunkDebugger:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "ChunkDebugger requires graphviz. Install with: pip install treesitter-chunker[viz]"
                )

        class NodeExplorer:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "NodeExplorer requires graphviz. Install with: pip install treesitter-chunker[viz]"
                )

        class QueryDebugger:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "QueryDebugger requires graphviz. Install with: pip install treesitter-chunker[viz]"
                )

        def highlight_chunk_boundaries(*args, **kwargs):
            raise ImportError(
                "highlight_chunk_boundaries requires graphviz. Install with: pip install treesitter-chunker[viz]"
            )

        def print_ast_tree(*args, **kwargs):
            raise ImportError(
                "print_ast_tree requires graphviz. Install with: pip install treesitter-chunker[viz]"
            )

        def render_ast_graph(*args, **kwargs):
            raise ImportError(
                "render_ast_graph requires graphviz. Install with: pip install treesitter-chunker[viz]"
            )

        class DebugREPL:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "DebugREPL requires graphviz. Install with: pip install treesitter-chunker[viz]"
                )

        def get_parser(*args, **kwargs):
            raise ImportError(
                "get_parser requires graphviz. Install with: pip install treesitter-chunker[viz]"
            )

        HAS_DEBUG_MODULES = False
    else:
        raise

app = typer.Typer(help="Debug and visualization tools for Tree-sitter chunker")
console = Console()


@app.command()
def repl(
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Initial language to use",
    ),
    file_path: Path | None = typer.Option(
        None,
        "--file_path",
        "-f",
        help="Initial file_path to load",
    ),
):
    """Start interactive debugging REPL."""
    if not HAS_DEBUG_MODULES:
        console.print(
            "[red]Debug commands require graphviz. Install with: pip install treesitter-chunker[viz][/red]"
        )
        raise typer.Exit(1)

    console.print("[bold cyan]Starting Tree-sitter Debug REPL...[/bold cyan]")

    # Start REPL

    repl_instance = DebugREPL()

    # Set initial language if provided
    if language:
        repl_instance._set_language(language)

    # Load initial file_path if provided
    if file_path:
        repl_instance._load_file(str(file_path))

    repl_instance.start()


@app.command()
def ast(
    file_path: Path = typer.Argument(..., exists=True, readable=True),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language (auto-detect if not specified)",
    ),
    fmt: str = typer.Option(
        "tree",
        "--fmt",
        "-f",
        help="Output fmt: tree, graph, json",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file_path (for graph fmt)",
    ),
    max_depth: int | None = typer.Option(
        None,
        "--depth",
        "-d",
        help="Maximum tree depth to display",
    ),
    highlight: str | None = typer.Option(
        None,
        "--highlight",
        "-h",
        help="Node types to highlight (comma-separated)",
    ),
    chunks: bool = typer.Option(False, "--chunks", "-c", help="Show chunk boundaries"),
    no_positions: bool = typer.Option(
        False,
        "--no-positions",
        help="Hide position information",
    ),
):
    """Visualize AST for a source file_path."""
    if not HAS_DEBUG_MODULES:
        console.print(
            "[red]Debug commands require graphviz. Install with: pip install treesitter-chunker[viz][/red]"
        )
        raise typer.Exit(1)

    # Auto-detect language
    if not language:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".c": "c",
            ".cpp": "cpp",
            ".rs": "rust",
        }
        language = ext_map.get(file_path.suffix.lower())
        if not language:
            console.print(
                "[red]Could not detect language. Please specify with --lang[/red]",
            )
            raise typer.Exit(1)

    # Get chunks if requested
    chunks_list = None
    if chunks:
        try:
            chunks_list = chunk_file(str(file_path), language)
        except (FileNotFoundError, IndexError, KeyError) as e:
            console.print(f"[yellow]Warning: Could not get chunks: {e}[/yellow]")

    # Parse highlight nodes
    highlight_nodes = None
    if highlight:
        highlight_nodes = {n.strip() for n in highlight.split(",")}

    try:
        if fmt == "tree":
            print_ast_tree(
                str(file_path),
                language,
                chunks=chunks_list,
                max_depth=max_depth,
                show_positions=not no_positions,
                highlight_nodes=highlight_nodes,
            )
        elif fmt == "graph":
            if output:
                render_ast_graph(
                    str(file_path),
                    language,
                    output_path=str(output),
                    chunks=chunks_list,
                    highlight_nodes=highlight_nodes,
                )
                console.print(f"[green]Graph saved to: {output}[/green]")
            else:
                # Print graph source
                source = render_ast_graph(
                    str(file_path),
                    language,
                    chunks=chunks_list,
                    highlight_nodes=highlight_nodes,
                )
                console.print(source)
        elif fmt == "json":
            visualizer = ASTVisualizer(language)
            json_output = visualizer.visualize_file(
                str(file_path),
                output_format="json",
                chunks=chunks_list,
                max_depth=max_depth,
            )
            print(json_output)
        else:
            console.print(f"[red]Unknown fmt: {fmt}[/red]")
            raise typer.Exit(1)

    except (FileNotFoundError, IndexError, KeyError) as e:
        console.print(f"[red]Error visualizing AST: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def query(
    query_string: str = typer.Argument(..., help="Tree-sitter query string"),
    file_path: Path | None = typer.Option(
        None,
        "--file_path",
        "-f",
        help="Source file_path to query",
    ),
    code: str | None = typer.Option(None, "--code", "-c", help="Inline code to query"),
    language: str = typer.Option(..., "--lang", "-l", help="Programming language"),
    show_ast: bool = typer.Option(False, "--ast", help="Show AST before query results"),
    no_captures: bool = typer.Option(
        False,
        "--no-captures",
        help="Hide capture details",
    ),
    no_highlight: bool = typer.Option(
        False,
        "--no-highlight",
        help="Don't highlight matches in source",
    ),
):
    """Debug a Tree-sitter query."""
    # Get source code
    if file_path:
        with Path(file_path).open(encoding="utf-8") as f:
            source_code = f.read()
    elif code:
        source_code = code
    else:
        console.print("[red]Please provide either --file_path or --code[/red]")
        raise typer.Exit(1)

    # Debug query
    try:
        debugger = QueryDebugger(language)
        debugger.debug_query(
            query_string,
            source_code,
            show_ast=show_ast,
            show_captures=not no_captures,
            highlight_matches=not no_highlight,
        )
    except (OSError, FileNotFoundError, IndexError) as e:
        console.print(f"[red]Query error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def chunks(
    file_path: Path = typer.Argument(..., exists=True, readable=True),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language (auto-detect if not specified)",
    ),
    show_decisions: bool = typer.Option(
        True,
        "--decisions/--no-decisions",
        help="Show chunking decisions",
    ),
    show_overlap: bool = typer.Option(
        True,
        "--overlap/--no-overlap",
        help="Check for overlapping chunks",
    ),
    show_gaps: bool = typer.Option(
        True,
        "--gaps/--no-gaps",
        help="Check for coverage gaps",
    ),
    max_size: int | None = typer.Option(
        None,
        "--max-size",
        help="Flag chunks exceeding this size",
    ),
    min_size: int | None = typer.Option(
        None,
        "--min-size",
        help="Flag chunks below this size",
    ),
    visualize: bool = typer.Option(
        False,
        "--visualize",
        "-v",
        help="Visualize chunk boundaries",
    ),
    side_by_side: bool = typer.Option(
        False,
        "--side-by-side",
        help="Show original and chunked side by side",
    ),
):
    """Analyze and debug chunking decisions."""
    if not HAS_DEBUG_MODULES:
        console.print(
            "[red]Debug commands require graphviz. Install with: pip install treesitter-chunker[viz][/red]"
        )
        raise typer.Exit(1)

    # Auto-detect language
    if not language:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".c": "c",
            ".cpp": "cpp",
            ".rs": "rust",
        }
        language = ext_map.get(file_path.suffix.lower())
        if not language:
            console.print(
                "[red]Could not detect language. Please specify with --lang[/red]",
            )
            raise typer.Exit(1)

    try:
        if visualize:
            # Show chunk visualization
            highlight_chunk_boundaries(
                str(file_path),
                language,
                show_stats=True,
                show_side_by_side=side_by_side,
            )
        else:
            # Run chunk analysis
            debugger = ChunkDebugger(language)
            debugger.analyze_file(
                str(file_path),
                show_decisions=show_decisions,
                show_overlap=show_overlap,
                show_gaps=show_gaps,
                max_chunk_size=max_size,
                min_chunk_size=min_size,
            )
    except (FileNotFoundError, IndexError, KeyError) as e:
        console.print(f"[red]Error analyzing chunks: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def explore(
    file_path: Path | None = typer.Option(
        None,
        "--file_path",
        "-f",
        help="Source file_path to explore",
    ),
    code: str | None = typer.Option(
        None,
        "--code",
        "-c",
        help="Inline code to explore",
    ),
    language: str = typer.Option(..., "--lang", "-l", help="Programming language"),
):
    """Interactively explore AST nodes."""
    if not HAS_DEBUG_MODULES:
        console.print(
            "[red]Debug commands require graphviz. Install with: pip install treesitter-chunker[viz][/red]"
        )
        raise typer.Exit(1)

    # Get source code
    if file_path:
        with Path(file_path).open(encoding="utf-8") as f:
            source_code = f.read()
    elif code:
        source_code = code
    else:
        console.print("[red]Please provide either --file_path or --code[/red]")
        raise typer.Exit(1)

    try:
        explorer = NodeExplorer(language)
        explorer.explore_code(source_code)
    except (OSError, FileNotFoundError, IndexError) as e:
        console.print(f"[red]Error starting explorer: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def validate(
    file_path: Path = typer.Argument(..., exists=True, readable=True),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language (auto-detect if not specified)",
    ),
    show_errors: bool = typer.Option(
        True,
        "--errors/--no-errors",
        help="Show parse errors",
    ),
    show_missing: bool = typer.Option(
        True,
        "--missing/--no-missing",
        help="Show missing nodes",
    ),
):
    """Validate parsing and identify errors."""
    if not HAS_DEBUG_MODULES:
        console.print(
            "[red]Debug commands require graphviz. Install with: pip install treesitter-chunker[viz][/red]"
        )
        raise typer.Exit(1)

    # Auto-detect language
    if not language:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".c": "c",
            ".cpp": "cpp",
            ".rs": "rust",
        }
        language = ext_map.get(file_path.suffix.lower())
        if not language:
            console.print(
                "[red]Could not detect language. Please specify with --lang[/red]",
            )
            raise typer.Exit(1)

    try:

        # Parse file_path
        with Path(file_path).open(
            "rb",
        ) as f:
            content = f.read()

        parser = get_parser(language)
        tree = parser.parse(content)

        # Check for errors
        has_errors = False
        error_nodes = []
        missing_nodes = []

        def check_node(node):
            nonlocal has_errors
            if node.has_error:
                has_errors = True
                error_nodes.append(node)
            if node.is_missing:
                missing_nodes.append(node)
            for child in node.children:
                check_node(child)

        check_node(tree.root_node)

        if not has_errors and not missing_nodes:
            console.print("[green]✓ File parsed successfully with no errors[/green]")
        else:
            console.print("[red]✗ Parse errors found[/red]")

            if show_errors and error_nodes:
                console.print(f"\n[bold]Error nodes ({len(error_nodes)}):[/bold]")
                for node in error_nodes[:10]:  # Show first 10
                    console.print(
                        f"  • {node.type} at {node.start_point[0]}:{node.start_point[1]}",
                    )

            if show_missing and missing_nodes:
                console.print(f"\n[bold]Missing nodes ({len(missing_nodes)}):[/bold]")
                for node in missing_nodes[:10]:  # Show first 10
                    console.print(
                        f"  • {node.type} at {node.start_point[0]}:{node.start_point[1]}",
                    )

    except (FileNotFoundError, IndexError, KeyError) as e:
        console.print(f"[red]Error validating file_path: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
