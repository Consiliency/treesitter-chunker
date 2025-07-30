from __future__ import annotations
from collections.abc import Iterator

import fnmatch
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomllib
import typer
from rich import print
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TimeRemainingColumn
from rich.table import Table

from chunker import chunk_file
from chunker.exceptions import ChunkerError
from chunker.parser import list_languages

app = typer.Typer(help="Tree‑sitter‑based code‑chunker CLI")
console = Console()

# Import debug commands
from .debug import commands as debug_commands

app.add_typer(debug_commands.app, name="debug", help="Debug and visualization tools")

# Import repo commands
from .repo_command import app as repo_app

if TYPE_CHECKING:

app.add_typer(repo_app, name="repo", help="Repository processing commands")


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration from .chunkerrc file_path."""
    config = {}

    # Look for config file_path
    if config_path:
        config_files = [config_path]
    else:
        config_files = [
            Path.cwd() / ".chunkerrc",
            Path.home() / ".chunkerrc",
        ]

    for config_file in config_files:
        if config_file.exists():
            try:
                with Path(config_file).open("rb") as f:
                    config = tomllib.load(f)
                break
            except (OSError, FileNotFoundError, IndexError) as e:
                console.print(
                    f"[yellow]Warning: Failed to load config from {config_file}: {e}[/yellow]",
                )

    return config


def get_files_from_patterns(
    patterns: list[str],
    base_path: Path = Path.cwd(),
) -> Iterator[Path]:
    """Get files matching glob patterns."""
    for pattern in patterns:
        # Handle recursive glob patterns
        if "**" in pattern:
            for path in base_path.rglob(pattern.replace("**/", "")):
                if path.is_file():
                    yield path
        else:
            for path in base_path.glob(pattern):
                if path.is_file():
                    yield path


def should_include_file(
    file_path: Path,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> bool:
    """Check if file_path should be included based on patterns."""
    file_str = str(file_path)

    # If include patterns specified, file_path must match at least one
    if include_patterns and not any(fnmatch.fnmatch(file_str, pattern) for pattern in include_patterns):
            return False

    # If exclude patterns specified, file_path must not match any
    if exclude_patterns and any(fnmatch.fnmatch(file_str, pattern) for pattern in exclude_patterns):
            return False

    return True


def process_file(
    file_path: Path,
    language: str | None,
    chunk_types: list[str] | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
) -> list[dict[str, Any]]:
    """Process a single file_path and return chunks."""
    # Auto-detect language if not specified
    if not language:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "javascript",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".rs": "rust",
        }
        ext = file_path.suffix.lower()
        language = ext_map.get(ext)
        if not language:
            return []

    try:
        chunks = chunk_file(file_path, language)
        results = []

        for chunk in chunks:
            # Apply chunk type filter
            if chunk_types and chunk.node_type not in chunk_types:
                continue

            # Apply size filters
            chunk_size = chunk.end_line - chunk.start_line + 1
            if min_size and chunk_size < min_size:
                continue
            if max_size and chunk_size > max_size:
                continue

            results.append(
                {
                    "file_path": str(file_path),
                    "language": language,
                    "node_type": chunk.node_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "size": chunk_size,
                    "parent_context": chunk.parent_context,
                    "content": chunk.content,
                },
            )

        return results
    except ChunkerError as e:
        console.print(f"[red]Error processing {file_path}: {e}[/red]")
        return []


@app.command()
def chunk(
    file_path: Path = typer.Argument(..., exists=True, readable=True),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language name (auto-detect if not specified)",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of Rich table",
    ),
    chunk_types: str | None = typer.Option(
        None,
        "--types",
        "-t",
        help="Comma-separated list of chunk types to include",
    ),
    min_size: int | None = typer.Option(
        None,
        "--min-size",
        help="Minimum chunk size in lines",
    ),
    max_size: int | None = typer.Option(
        None,
        "--max-size",
        help="Maximum chunk size in lines",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file_path",
    ),
):
    """Chunk a single source file_path."""
    # Load config
    cfg = load_config(config)

    # Parse chunk types
    types_list = None
    if chunk_types:
        types_list = [t.strip() for t in chunk_types.split(",")]
    elif "chunk_types" in cfg:
        types_list = cfg["chunk_types"]

    # Get size limits from config if not specified
    if min_size is None and "min_chunk_size" in cfg:
        min_size = cfg["min_chunk_size"]
    if max_size is None and "max_chunk_size" in cfg:
        max_size = cfg["max_chunk_size"]

    results = process_file(file_path, language, types_list, min_size, max_size)

    if json_out:
        print(json.dumps(results, indent=2))
    else:
        tbl = Table(title=f"Chunks in {file_path}")
        tbl.add_column("#", justify="right")
        tbl.add_column("Node")
        tbl.add_column("Lines")
        tbl.add_column("Size", justify="right")
        tbl.add_column("Parent")
        for i, chunk in enumerate(results, 1):
            tbl.add_row(
                str(i),
                chunk["node_type"],
                f"{chunk['start_line']}-{chunk['end_line']}",
                str(chunk["size"]),
                chunk["parent_context"],
            )
        console.print(tbl)


@app.command()
def batch(
    paths: list[Path] | None = typer.Argument(
        None,
        help="Files or directories to process",
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Glob pattern for files",
    ),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language name (auto-detect if not specified)",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON/JSONL"),
    jsonl: bool = typer.Option(
        False,
        "--jsonl",
        help="Output as JSONL (one JSON per line)",
    ),
    chunk_types: str | None = typer.Option(
        None,
        "--types",
        "-t",
        help="Comma-separated list of chunk types",
    ),
    min_size: int | None = typer.Option(
        None,
        "--min-size",
        help="Minimum chunk size in lines",
    ),
    max_size: int | None = typer.Option(
        None,
        "--max-size",
        help="Maximum chunk size in lines",
    ),
    include: str | None = typer.Option(
        None,
        "--include",
        "-i",
        help="Include file_path patterns (comma-separated)",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Exclude file_path patterns (comma-separated)",
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        "-r/-R",
        help="Recursively process directories",
    ),
    parallel: int | None = typer.Option(
        None,
        "--parallel",
        "-j",
        help="Number of parallel workers",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file_path",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
    from_stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read file_path paths from stdin",
    ),
):
    """Process multiple files with batch operations."""
    # Load config
    cfg = load_config(config)

    # Parse options
    types_list = None
    if chunk_types:
        types_list = [t.strip() for t in chunk_types.split(",")]
    elif "chunk_types" in cfg:
        types_list = cfg["chunk_types"]

    include_patterns = None
    if include:
        include_patterns = [p.strip() for p in include.split(",")]
    elif "include_patterns" in cfg:
        include_patterns = cfg["include_patterns"]

    exclude_patterns = None
    if exclude:
        exclude_patterns = [p.strip() for p in exclude.split(",")]
    elif "exclude_patterns" in cfg:
        exclude_patterns = cfg["exclude_patterns"]

    # Get size limits
    if min_size is None and "min_chunk_size" in cfg:
        min_size = cfg["min_chunk_size"]
    if max_size is None and "max_chunk_size" in cfg:
        max_size = cfg["max_chunk_size"]

    # Get parallel workers
    if parallel is None:
        parallel = cfg.get("parallel_workers", os.cpu_count() or 1)

    # Collect files to process
    files_to_process = []

    if from_stdin:
        # Read file_path paths from stdin
        for line in sys.stdin:
            path = Path(line.strip())
            if path.exists() and path.is_file() and should_include_file(path, include_patterns, exclude_patterns):
                    files_to_process.append(path)
    # Process provided paths
    elif not paths and pattern:
        # Use pattern to find files
        for file_path in get_files_from_patterns([pattern]):
            if should_include_file(file_path, include_patterns, exclude_patterns):
                files_to_process.append(file_path)
    elif paths:
        # Process provided paths
        for path in paths:
            if path.is_file() and should_include_file(path, include_patterns, exclude_patterns):
                    files_to_process.append(path)
            elif path.is_dir():
                # Process directory
                if recursive:
                    for file_path in path.rglob("*"):
                        if file_path.is_file() and should_include_file(
                            file_path,
                            include_patterns,
                            exclude_patterns,
                        ):
                            files_to_process.append(file_path)
                else:
                    for file_path in path.iterdir():
                        if file_path.is_file() and should_include_file(
                            file_path,
                            include_patterns,
                            exclude_patterns,
                        ):
                            files_to_process.append(file_path)
    else:
        console.print(
            "[red]Error: No files specified. Use paths, --pattern, or --stdin[/red]",
        )
        raise typer.Exit(1)

    if not files_to_process:
        console.print("[yellow]No files to process[/yellow]")
        return

    # Process files
    all_results = []

    def process_with_progress(file_path: Path):
        return process_file(file_path, language, types_list, min_size, max_size)

    if quiet:
        # Process without progress bar
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(process_with_progress, f): f for f in files_to_process
            }
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
    else:
        # Process with progress bar
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Processing files...",
                total=len(files_to_process),
            )

            with ThreadPoolExecutor(max_workers=parallel) as executor:
                futures = {
                    executor.submit(process_with_progress, f): f
                    for f in files_to_process
                }
                for future in as_completed(futures):
                    results = future.result()
                    all_results.extend(results)
                    progress.advance(task)

    # Output results
    if jsonl:
        for result in all_results:
            print(json.dumps(result))
    elif json_out:
        print(json.dumps(all_results, indent=2))
    else:
        # Summary table
        summary = {}
        total_chunks = len(all_results)

        for result in all_results:
            lang = result["language"]
            node_type = result["node_type"]
            key = f"{lang}:{node_type}"
            summary[key] = summary.get(key, 0) + 1

        tbl = Table(
            title=f"Chunk Summary ({total_chunks} total chunks from {len(files_to_process)} files)",
        )
        tbl.add_column("Language", style="cyan")
        tbl.add_column("Node Type", style="green")
        tbl.add_column("Count", justify="right", style="yellow")

        for key in sorted(summary.keys()):
            lang, node_type = key.split(":", 1)
            tbl.add_row(lang, node_type, str(summary[key]))

        console.print(tbl)


@app.command()
def languages():
    """List available languages."""
    try:
        langs = list_languages()
        tbl = Table(title="Available Languages")
        tbl.add_column("Language", style="cyan")
        tbl.add_column("Status", style="green")

        for lang in sorted(langs):
            tbl.add_row(lang, "✓ Available")

        console.print(tbl)
    except (IndexError, KeyError, TypeError) as e:
        console.print(f"[red]Error listing languages: {e}[/red]")


if __name__ == "__main__":
    app()
