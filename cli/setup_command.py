"""Setup command for tree-sitter grammar compilation.

This module provides CLI commands for setting up tree-sitter grammars,
including fetching, building, and validating grammar libraries.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Sequence

app = typer.Typer(help="Grammar setup and management commands")
console = Console()

# Default languages included in prebuilt wheels
DEFAULT_LANGUAGES = ["python", "javascript", "rust"]

# Extended language set for full setup
EXTENDED_LANGUAGES = [
    "python",
    "javascript",
    "typescript",
    "rust",
    "c",
    "cpp",
    "go",
    "java",
    "ruby",
    "php",
]

# Repository URLs for grammar sources
GRAMMAR_REPOS = {
    "python": "https://github.com/tree-sitter/tree-sitter-python",
    "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
    "typescript": "https://github.com/tree-sitter/tree-sitter-typescript",
    "rust": "https://github.com/tree-sitter/tree-sitter-rust",
    "c": "https://github.com/tree-sitter/tree-sitter-c",
    "cpp": "https://github.com/tree-sitter/tree-sitter-cpp",
    "go": "https://github.com/tree-sitter/tree-sitter-go",
    "java": "https://github.com/tree-sitter/tree-sitter-java",
    "ruby": "https://github.com/tree-sitter/tree-sitter-ruby",
    "php": "https://github.com/tree-sitter/tree-sitter-php",
    "bash": "https://github.com/tree-sitter/tree-sitter-bash",
    "html": "https://github.com/tree-sitter/tree-sitter-html",
    "css": "https://github.com/tree-sitter/tree-sitter-css",
    "json": "https://github.com/tree-sitter/tree-sitter-json",
    "yaml": "https://github.com/ikatyang/tree-sitter-yaml",
    "toml": "https://github.com/ikatyang/tree-sitter-toml",
    "markdown": "https://github.com/ikatyang/tree-sitter-markdown",
    "sql": "https://github.com/DerekStride/tree-sitter-sql",
    "kotlin": "https://github.com/fwcd/tree-sitter-kotlin",
    "swift": "https://github.com/alex-pinkus/tree-sitter-swift",
}


def get_default_dirs() -> tuple[Path, Path]:
    """Get default grammar and build directories.

    Returns:
        Tuple of (grammars_dir, build_dir)
    """
    # Check for environment override
    build_override = os.environ.get("CHUNKER_GRAMMAR_BUILD_DIR")
    if build_override:
        build_dir = Path(build_override)
        grammars_dir = build_dir.parent / "grammars"
    else:
        # Default to user cache directory
        cache_base = Path.home() / ".cache" / "treesitter-chunker"
        grammars_dir = cache_base / "grammars"
        build_dir = cache_base / "build"

    return grammars_dir, build_dir


def get_grammar_manager(
    grammars_dir: Path | None = None,
    build_dir: Path | None = None,
):
    """Get or create a TreeSitterGrammarManager instance.

    Args:
        grammars_dir: Directory for grammar sources
        build_dir: Directory for built grammars

    Returns:
        TreeSitterGrammarManager instance
    """
    from chunker.grammar.manager import TreeSitterGrammarManager

    if grammars_dir is None or build_dir is None:
        default_grammars, default_build = get_default_dirs()
        grammars_dir = grammars_dir or default_grammars
        build_dir = build_dir or default_build

    return TreeSitterGrammarManager(grammars_dir=grammars_dir, build_dir=build_dir)


@app.command("grammars")
def setup_grammars(
    languages: list[str] | None = typer.Argument(
        None,
        help="Languages to set up (default: python,javascript,rust)",
    ),
    *,
    all_extended: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Set up all extended languages (10 common languages)",
    ),
    grammars_dir: Path | None = typer.Option(
        None,
        "--grammars-dir",
        "-g",
        help="Directory for grammar sources",
    ),
    build_dir: Path | None = typer.Option(
        None,
        "--build-dir",
        "-b",
        help="Directory for built grammar libraries",
    ),
    fetch_only: bool = typer.Option(
        False,
        "--fetch-only",
        help="Only fetch sources, don't build",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-fetch and rebuild even if exists",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show verbose output",
    ),
):
    """Set up tree-sitter grammars for code parsing.

    This command fetches and compiles tree-sitter grammar libraries needed
    for parsing source code. By default, it sets up Python, JavaScript,
    and Rust grammars.

    Examples:
        # Set up default languages (python, javascript, rust)
        treesitter-chunker setup grammars

        # Set up specific languages
        treesitter-chunker setup grammars python go java

        # Set up all extended languages
        treesitter-chunker setup grammars --all

        # Custom directories
        treesitter-chunker setup grammars --grammars-dir ./grammars --build-dir ./build
    """
    # Determine which languages to set up
    if all_extended:
        target_languages = EXTENDED_LANGUAGES
    elif languages:
        target_languages = languages
    else:
        target_languages = DEFAULT_LANGUAGES

    # Validate languages
    invalid_langs = [lang for lang in target_languages if lang not in GRAMMAR_REPOS]
    if invalid_langs:
        console.print(
            f"[red]Unknown language(s): {', '.join(invalid_langs)}[/red]",
        )
        console.print(f"[yellow]Available: {', '.join(sorted(GRAMMAR_REPOS.keys()))}[/yellow]")
        raise typer.Exit(1)

    # Get directories
    if grammars_dir is None or build_dir is None:
        default_grammars, default_build = get_default_dirs()
        grammars_dir = grammars_dir or default_grammars
        build_dir = build_dir or default_build

    console.print(f"[cyan]Setting up grammars for: {', '.join(target_languages)}[/cyan]")
    console.print(f"[dim]Grammar sources: {grammars_dir}[/dim]")
    console.print(f"[dim]Build output: {build_dir}[/dim]")
    console.print()

    # Create manager
    try:
        mgr = get_grammar_manager(grammars_dir, build_dir)
    except Exception as e:
        console.print(f"[red]Failed to initialize grammar manager: {e}[/red]")
        raise typer.Exit(1) from e

    # Track results
    results: dict[str, dict[str, bool | str]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose,
    ) as progress:
        for lang in target_languages:
            results[lang] = {"fetched": False, "built": False, "error": ""}

            # Add grammar
            task = progress.add_task(f"[cyan]Adding {lang}...", total=None)
            try:
                repo_url = GRAMMAR_REPOS[lang]
                mgr.add_grammar(lang, repo_url)
                progress.update(task, description=f"[cyan]Fetching {lang}...")

                # Fetch grammar
                if mgr.fetch_grammar(lang):
                    results[lang]["fetched"] = True
                    progress.update(task, description=f"[green]Fetched {lang}")

                    if not fetch_only:
                        progress.update(task, description=f"[cyan]Building {lang}...")
                        if mgr.build_grammar(lang):
                            results[lang]["built"] = True
                            progress.update(task, description=f"[green]Built {lang}")
                        else:
                            results[lang]["error"] = "Build failed"
                            progress.update(
                                task, description=f"[yellow]Build failed: {lang}",
                            )
                else:
                    results[lang]["error"] = "Fetch failed"
                    progress.update(task, description=f"[red]Fetch failed: {lang}")

            except Exception as e:
                results[lang]["error"] = str(e)
                progress.update(task, description=f"[red]Error: {lang} - {e}")
                if verbose:
                    console.print_exception()

            progress.remove_task(task)

    # Summary table
    console.print()
    table = Table(title="Grammar Setup Results")
    table.add_column("Language", style="cyan")
    table.add_column("Fetched", justify="center")
    table.add_column("Built", justify="center")
    table.add_column("Status")

    success_count = 0
    for lang, result in results.items():
        fetched = "[green]✓[/green]" if result["fetched"] else "[red]✗[/red]"
        built = "[green]✓[/green]" if result["built"] else (
            "[dim]-[/dim]" if fetch_only else "[red]✗[/red]"
        )

        if result["error"]:
            status = f"[red]{result['error']}[/red]"
        elif result["built"] or (fetch_only and result["fetched"]):
            status = "[green]Success[/green]"
            success_count += 1
        else:
            status = "[yellow]Incomplete[/yellow]"

        table.add_row(lang, fetched, built, status)

    console.print(table)

    # Final summary
    total = len(target_languages)
    if success_count == total:
        console.print(f"\n[green]✓ All {total} grammars set up successfully![/green]")
    else:
        console.print(
            f"\n[yellow]⚠ {success_count}/{total} grammars set up successfully[/yellow]",
        )

    # Show next steps
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  [dim]• Verify installation:[/dim] treesitter-chunker languages")
    console.print("  [dim]• Test parsing:[/dim] treesitter-chunker chunk example.py -l python")

    if success_count < total:
        raise typer.Exit(1)


@app.command("status")
def setup_status(
    grammars_dir: Path | None = typer.Option(
        None,
        "--grammars-dir",
        "-g",
        help="Directory for grammar sources",
    ),
    build_dir: Path | None = typer.Option(
        None,
        "--build-dir",
        "-b",
        help="Directory for built grammar libraries",
    ),
):
    """Show current grammar setup status.

    Displays which grammars are installed and their build status.
    """
    # Get directories
    if grammars_dir is None or build_dir is None:
        default_grammars, default_build = get_default_dirs()
        grammars_dir = grammars_dir or default_grammars
        build_dir = build_dir or default_build

    console.print("[cyan]Grammar Setup Status[/cyan]")
    console.print(f"[dim]Grammar sources: {grammars_dir}[/dim]")
    console.print(f"[dim]Build output: {build_dir}[/dim]")
    console.print()

    # Check directories exist
    if not grammars_dir.exists():
        console.print("[yellow]No grammar sources found.[/yellow]")
        console.print("[dim]Run 'treesitter-chunker setup grammars' to set up grammars.[/dim]")
        return

    # List installed grammars
    table = Table(title="Installed Grammars")
    table.add_column("Language", style="cyan")
    table.add_column("Source", justify="center")
    table.add_column("Built", justify="center")
    table.add_column("Path")

    # Check for grammar directories
    grammar_dirs = list(grammars_dir.glob("tree-sitter-*"))

    if not grammar_dirs:
        console.print("[yellow]No grammar sources found.[/yellow]")
        console.print("[dim]Run 'treesitter-chunker setup grammars' to set up grammars.[/dim]")
        return

    for grammar_path in sorted(grammar_dirs):
        # Extract language name
        lang_name = grammar_path.name.replace("tree-sitter-", "")

        # Check for source
        has_source = (grammar_path / "src" / "parser.c").exists() or (
            grammar_path / "grammar.js"
        ).exists()

        # Check for built library
        # Look for .so files in build directory
        built_lib = None
        for pattern in [f"{lang_name}.so", f"tree_sitter_{lang_name}.so", "*.so"]:
            matches = list(build_dir.glob(pattern))
            if matches:
                built_lib = matches[0]
                break

        source_status = "[green]✓[/green]" if has_source else "[red]✗[/red]"
        built_status = "[green]✓[/green]" if built_lib else "[red]✗[/red]"

        table.add_row(
            lang_name,
            source_status,
            built_status,
            str(grammar_path.relative_to(grammars_dir.parent)),
        )

    console.print(table)

    # Also check what languages are available through the parser
    try:
        from chunker.parser import list_languages

        available = list_languages()
        if available:
            console.print(f"\n[green]Languages available for parsing:[/green] {', '.join(sorted(available))}")
    except Exception:
        pass


@app.command("clean")
def setup_clean(
    grammars_dir: Path | None = typer.Option(
        None,
        "--grammars-dir",
        "-g",
        help="Directory for grammar sources",
    ),
    build_dir: Path | None = typer.Option(
        None,
        "--build-dir",
        "-b",
        help="Directory for built grammar libraries",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Remove both sources and built files",
    ),
    sources_only: bool = typer.Option(
        False,
        "--sources",
        help="Only remove source directories",
    ),
    builds_only: bool = typer.Option(
        False,
        "--builds",
        help="Only remove built libraries",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
):
    """Clean up grammar files.

    Removes downloaded grammar sources and/or compiled libraries.
    """
    import shutil

    # Get directories
    if grammars_dir is None or build_dir is None:
        default_grammars, default_build = get_default_dirs()
        grammars_dir = grammars_dir or default_grammars
        build_dir = build_dir or default_build

    # Determine what to clean
    if not (all_files or sources_only or builds_only):
        # Default: clean builds only
        builds_only = True

    to_clean = []
    if all_files or sources_only:
        if grammars_dir.exists():
            to_clean.append(("Grammar sources", grammars_dir))
    if all_files or builds_only:
        if build_dir.exists():
            to_clean.append(("Built libraries", build_dir))

    if not to_clean:
        console.print("[yellow]Nothing to clean.[/yellow]")
        return

    # Show what will be removed
    console.print("[cyan]The following will be removed:[/cyan]")
    for desc, path in to_clean:
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        size_mb = size / (1024 * 1024)
        console.print(f"  • {desc}: {path} ({size_mb:.1f} MB)")

    if not force:
        if not typer.confirm("\nProceed with cleanup?"):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Perform cleanup
    for desc, path in to_clean:
        try:
            shutil.rmtree(path)
            console.print(f"[green]✓ Removed {desc}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to remove {desc}: {e}[/red]")


@app.command("list-available")
def list_available():
    """List all available grammars that can be installed."""
    table = Table(title="Available Grammar Sources")
    table.add_column("Language", style="cyan")
    table.add_column("Repository")
    table.add_column("Category")

    # Categorize languages
    official = [
        "python", "javascript", "typescript", "rust", "c", "cpp",
        "go", "java", "ruby", "php", "bash", "html", "css", "json",
    ]
    community = ["yaml", "toml", "markdown", "sql", "kotlin", "swift"]

    for lang in sorted(GRAMMAR_REPOS.keys()):
        repo = GRAMMAR_REPOS[lang]
        category = "[green]Official[/green]" if lang in official else "[blue]Community[/blue]"
        table.add_row(lang, repo, category)

    console.print(table)
    console.print(f"\n[dim]Total: {len(GRAMMAR_REPOS)} languages available[/dim]")
    console.print("[dim]Install with: treesitter-chunker setup grammars <language>[/dim]")


if __name__ == "__main__":
    app()
