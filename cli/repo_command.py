"""Repository processing CLI command."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from chunker.repo.processor import GitAwareRepoProcessor

app = typer.Typer(help="Process entire repositories")
console = Console()


@app.command()
def process(
    repo_path: str = typer.Argument(help="Path to repository"),
    incremental: bool = typer.Option(True, help="Only process changed files"),
    file_pattern: str | None = typer.Option(
        None,
        help="Glob pattern for files to include",
    ),
    exclude: list[str] | None = typer.Option(None, help="Patterns to exclude"),
    output: Path | None = typer.Option(
        None,
        help="Output file_path for results (JSON)",
    ),
    max_workers: int = typer.Option(4, help="Maximum parallel workers"),
    no_progress: bool = typer.Option(False, help="Disable progress bar"),
    traversal: str = typer.Option(
        "depth-first",
        help="Traversal strategy: depth-first or breadth-first",
    ),
):
    """Process all files in a repository."""

    # Create processor
    processor = GitAwareRepoProcessor(
        max_workers=max_workers,
        show_progress=not no_progress,
        traversal_strategy=traversal,
    )

    try:
        # Process repository
        console.print(f"[cyan]Processing repository: {repo_path}[/cyan]")

        result = processor.process_repository(
            repo_path,
            incremental=incremental,
            file_pattern=file_pattern,
            exclude_patterns=exclude,
        )

        # Display results
        console.print("\n[green]✓ Processing complete![/green]")

        # Summary table
        table = Table(title="Repository Processing Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Total Files", str(result.total_files))
        table.add_row("Processed Files", str(len(result.file_results)))
        table.add_row("Total Chunks", str(result.total_chunks))
        table.add_row("Skipped Files", str(len(result.skipped_files)))
        table.add_row("Errors", str(len(result.errors)))
        table.add_row("Processing Time", f"{result.processing_time:.2f} seconds")

        console.print(table)

        # Show errors if any
        if result.errors:
            console.print("\n[red]Errors encountered:[/red]")
            for file_path, error in list(result.errors.items())[:5]:
                console.print(f"  • {file_path}: {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

        # Save to file_path if requested
        if output:
            output_data = {
                "repo_path": result.repo_path,
                "total_files": result.total_files,
                "total_chunks": result.total_chunks,
                "processing_time": result.processing_time,
                "metadata": result.metadata,
                "files": [],
            }

            for file_result in result.file_results:
                file_data = {
                    "path": file_result.file_path,
                    "processing_time": file_result.processing_time,
                    "chunks": [],
                }

                for chunk in file_result.chunks:
                    chunk_data = {
                        "type": chunk.chunk_type,
                        "name": chunk.name,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "size": len(chunk.content),
                        "metadata": chunk.metadata,
                    }
                    file_data["chunks"].append(chunk_data)

                output_data["files"].append(file_data)

            with Path(output).open(
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(output_data, f, indent=2)

            console.print(f"\n[green]Results saved to: {output}[/green]")

    except (OSError, FileNotFoundError, IndexError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def estimate(
    repo_path: str = typer.Argument(help="Path to repository"),
):
    """Estimate processing time for a repository."""

    processor = GitAwareRepoProcessor(show_progress=False)

    try:
        console.print(f"[cyan]Analyzing repository: {repo_path}[/cyan]")

        # Get file_path list
        files = processor.get_processable_files(repo_path)

        # Estimate time
        estimated_time = processor.estimate_processing_time(repo_path)

        # Display results
        console.print("\n[green]Repository Analysis:[/green]")
        console.print(f"  • Processable files: {len(files)}")
        console.print(f"  • Estimated time: {estimated_time:.1f} seconds")

        # Show file_path breakdown by language
        lang_counts = {}
        for file_path in files:
            ext = file_path.suffix.lower()
            lang = processor._language_extensions.get(ext, "unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        if lang_counts:
            console.print("\n[cyan]Files by language:[/cyan]")
            for lang, count in sorted(lang_counts.items()):
                console.print(f"  • {lang}: {count} files")

    except (AttributeError, FileNotFoundError, IndexError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def changed(
    repo_path: str = typer.Argument(help="Path to repository"),
    since: str | None = typer.Option(
        None,
        help="Show changes since this commit (e.g., HEAD~1)",
    ),
    branch: str | None = typer.Option(None, help="Compare with this branch"),
):
    """Show files that would be processed in incremental mode."""

    processor = GitAwareRepoProcessor(show_progress=False)

    try:
        console.print(f"[cyan]Checking changes in: {repo_path}[/cyan]")

        # Get changed files
        changed_files = processor.get_changed_files(
            repo_path,
            since_commit=since,
            branch=branch,
        )

        if changed_files:
            console.print(f"\n[yellow]Changed files ({len(changed_files)}):[/yellow]")
            for file_path in sorted(changed_files):
                console.print(f"  • {file_path}")
        else:
            console.print("\n[green]No changes detected[/green]")

    except (FileNotFoundError, IndexError, KeyError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
