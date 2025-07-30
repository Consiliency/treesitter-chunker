"""
Interactive REPL for Tree-sitter debugging.
"""

import tempfile
import traceback
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from chunker.debug.visualization.ast_visualizer import ASTVisualizer
from chunker.parser import list_languages

from .chunk_debugger import ChunkDebugger
from .node_explorer import NodeExplorer
from .query_debugger import QueryDebugger


class DebugREPL:
    """Interactive REPL for Tree-sitter debugging."""

    def __init__(self):
        """Initialize REPL."""
        self.console = Console()
        self.current_language: str | None = None
        self.current_file: str | None = None
        self.current_code: str | None = None
        self.query_debugger: QueryDebugger | None = None
        self.chunk_debugger: ChunkDebugger | None = None
        self.node_explorer: NodeExplorer | None = None
        self.history: list = []

    def start(self) -> None:
        """Start the REPL."""
        self._show_banner()
        self._main_loop()

    def _show_banner(self) -> None:
        """Show welcome banner."""
        banner = """
[bold cyan]Tree-sitter Debug REPL[/bold cyan]
[dim]Interactive debugging environment for Tree-sitter ASTs and chunking[/dim]

Available commands:
  [green]lang <language>[/green]     - Set current language
  [green]load <file>[/green]        - Load a file for analysis
  [green]code <code>[/green]        - Set code directly
  [green]query <query>[/green]      - Debug a Tree-sitter query
  [green]chunk[/green]              - Analyze chunking
  [green]explore[/green]            - Explore AST interactively
  [green]ast[/green]                - Show AST tree
  [green]languages[/green]          - List available languages
  [green]help[/green]               - Show detailed help
  [green]quit[/green]               - Exit REPL
"""
        self.console.print(Panel(banner, expand=False))

    def _main_loop(self) -> None:
        """Main REPL loop."""
        while True:
            try:
                # Build prompt
                prompt_parts = ["treesitter"]
                if self.current_language:
                    prompt_parts.append(f"[{self.current_language}]")
                if self.current_file:
                    prompt_parts.append(f"({Path(self.current_file).name})")

                prompt = f"[cyan]{':'.join(prompt_parts)}>[/cyan] "

                # Get command
                command = Prompt.ask(prompt).strip()

                if not command:
                    continue

                # Add to history
                self.history.append(command)

                # Parse command
                parts = command.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                # Execute command
                if cmd in ["q", "quit", "exit"]:
                    if Confirm.ask("Exit REPL?"):
                        break
                elif cmd == "help":
                    self._show_help()
                elif cmd == "lang":
                    self._set_language(args)
                elif cmd == "languages":
                    self._list_languages()
                elif cmd == "load":
                    self._load_file(args)
                elif cmd == "code":
                    self._set_code(args)
                elif cmd == "query":
                    self._debug_query(args)
                elif cmd == "chunk":
                    self._analyze_chunks()
                elif cmd == "explore":
                    self._explore_ast()
                elif cmd == "ast":
                    self._show_ast()
                elif cmd == "clear":
                    self.console.clear()
                elif cmd == "history":
                    self._show_history()
                elif cmd == "save":
                    self._save_session(args)
                elif cmd == "info":
                    self._show_info()
                else:
                    self.console.print(f"[red]Unknown command: {cmd}[/red]")
                    self.console.print("Type 'help' for available commands")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except (FileNotFoundError, IndexError, KeyError) as e:
                self.console.print(f"[red]Error: {e}[/red]")
                if self.console.is_terminal:
                    traceback.print_exc()

    def _show_help(self) -> None:
        """Show detailed help."""
        help_text = """
[bold]Language and File Commands:[/bold]
  [green]lang <language>[/green]     Set the current programming language
  [green]languages[/green]          List all available languages
  [green]load <file>[/green]        Load a file for analysis
  [green]code <code>[/green]        Set code directly (or multiline mode)
  [green]info[/green]               Show current session info

[bold]Debugging Commands:[/bold]
  [green]query <query>[/green]      Debug a Tree-sitter query
  [green]chunk[/green]              Analyze chunking for current code
  [green]explore[/green]            Explore AST interactively
  [green]ast[/green]                Show AST tree view

[bold]Utility Commands:[/bold]
  [green]history[/green]            Show command history
  [green]save <file>[/green]        Save session to file
  [green]clear[/green]              Clear screen
  [green]help[/green]               Show this help
  [green]quit[/green]               Exit REPL

[bold]Query Syntax:[/bold]
  Use standard Tree-sitter query syntax:
  - (node_type) for nodes
  - @capture.name for captures
  - (#predicate? @capture) for predicates

[bold]Examples:[/bold]
  lang python
  load example.py
  query (function_definition name: (identifier) @func)
  chunk
  explore
"""
        self.console.print(Panel(help_text, title="Help", expand=False))

    def _set_language(self, language: str) -> None:
        """Set current language."""
        if not language:
            self.console.print("[red]Please specify a language[/red]")
            return

        available = list_languages()
        if language not in available:
            self.console.print(f"[red]Unknown language: {language}[/red]")
            self.console.print(f"Available: {', '.join(available)}")
            return

        self.current_language = language
        self.query_debugger = QueryDebugger(language)
        self.chunk_debugger = ChunkDebugger(language)
        self.node_explorer = NodeExplorer(language)

        self.console.print(f"[green]Language set to: {language}[/green]")

    def _list_languages(self) -> None:
        """List available languages."""
        languages = list_languages()
        self.console.print("[bold]Available languages:[/bold]")
        for lang in sorted(languages):
            marker = "●" if lang == self.current_language else "○"
            self.console.print(f"  {marker} {lang}")

    def _load_file(self, file_path: str) -> None:
        """Load a file for analysis."""
        if not file_path:
            self.console.print("[red]Please specify a file path[/red]")
            return

        try:
            with Path(file_path).open(encoding="utf-8") as f:
                self.current_code = f.read()
            self.current_file = file_path

            # Auto-detect language if not set
            if not self.current_language:
                ext = Path(file_path).suffix.lower()
                lang_map = {
                    ".py": "python",
                    ".js": "javascript",
                    ".c": "c",
                    ".cpp": "cpp",
                    ".cc": "cpp",
                    ".rs": "rust",
                }
                if ext in lang_map:
                    self._set_language(lang_map[ext])

            self.console.print(f"[green]Loaded: {file_path}[/green]")
            self.console.print(f"Size: {len(self.current_code)} bytes")

        except (FileNotFoundError, IndexError, KeyError) as e:
            self.console.print(f"[red]Failed to load file: {e}[/red]")

    def _set_code(self, code: str) -> None:
        """Set code directly."""
        if code:
            self.current_code = code
            self.current_file = None
        else:
            # Multiline input mode
            self.console.print("Enter code (Ctrl+D or empty line to finish):")
            lines = []
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                except EOFError:
                    break

            self.current_code = "\n".join(lines)
            self.current_file = None

        self.console.print(f"[green]Code set ({len(self.current_code)} bytes)[/green]")

    def _debug_query(self, query: str) -> None:
        """Debug a Tree-sitter query."""
        if not self._check_ready():
            return

        if not query:
            # Multiline query input
            self.console.print("Enter query (empty line to finish):")
            lines = []
            while True:
                line = input().strip()
                if not line:
                    break
                lines.append(line)
            query = "\n".join(lines)

        if not query:
            self.console.print("[red]No query provided[/red]")
            return

        self.query_debugger.debug_query(
            query,
            self.current_code,
            show_ast=False,
            show_captures=True,
            highlight_matches=True,
        )

    def _analyze_chunks(self) -> None:
        """Analyze chunking."""
        if not self._check_ready():
            return

        if self.current_file:
            self.chunk_debugger.analyze_file(
                self.current_file,
                show_decisions=True,
                show_overlap=True,
                show_gaps=True,
            )
        else:
            # Save to temp file

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=f".{self.current_language}",
                delete=False,
            ) as f:
                f.write(self.current_code)
                temp_path = f.name

            try:
                self.chunk_debugger.analyze_file(
                    temp_path,
                    show_decisions=True,
                    show_overlap=True,
                    show_gaps=True,
                )
            finally:
                Path(temp_path).unlink()

    def _explore_ast(self) -> None:
        """Start AST explorer."""
        if not self._check_ready():
            return

        self.node_explorer.explore_code(self.current_code)

    def _show_ast(self) -> None:
        """Show AST tree."""
        if not self._check_ready():
            return


        visualizer = ASTVisualizer(self.current_language)

        # Save to temp file

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=f".{self.current_language}",
            delete=False,
        ) as f:
            f.write(self.current_code)
            temp_path = f.name

        try:
            visualizer.visualize_file(
                temp_path,
                output_format="tree",
                max_depth=4,
                show_positions=True,
            )
        finally:
            Path(temp_path).unlink()

    def _show_history(self) -> None:
        """Show command history."""
        if not self.history:
            self.console.print("[yellow]No command history[/yellow]")
            return

        self.console.print("[bold]Command History:[/bold]")
        for i, cmd in enumerate(self.history[-20:], 1):  # Last 20
            self.console.print(f"  {i:3d}. {cmd}")

    def _save_session(self, file_path: str) -> None:
        """Save current session."""
        if not file_path:
            self.console.print("[red]Please specify a file path[/red]")
            return

        try:
            with Path(file_path).open("w") as f:
                f.write("# Tree-sitter Debug Session\n")
                f.write(f"# Language: {self.current_language or 'none'}\n")
                f.write(f"# File: {self.current_file or 'none'}\n\n")

                if self.current_code:
                    f.write("## Code:\n")
                    f.write(self.current_code)
                    f.write("\n\n")

                if self.history:
                    f.write("## Command History:\n")
                    for cmd in self.history:
                        f.write(f"{cmd}\n")

            self.console.print(f"[green]Session saved to: {file_path}[/green]")

        except (OSError, FileNotFoundError, IndexError) as e:
            self.console.print(f"[red]Failed to save: {e}[/red]")

    def _show_info(self) -> None:
        """Show current session info."""
        info = {
            "Language": self.current_language or "Not set",
            "File": self.current_file or "Not loaded",
            "Code Size": (
                f"{len(self.current_code)} bytes" if self.current_code else "No code"
            ),
            "Commands Run": str(len(self.history)),
        }

        self.console.print("[bold]Session Info:[/bold]")
        for key, value in info.items():
            self.console.print(f"  {key}: {value}")

    def _check_ready(self) -> bool:
        """Check if ready for operations."""
        if not self.current_language:
            self.console.print(
                "[red]Please set a language first (lang <language>)[/red]",
            )
            return False

        if not self.current_code:
            self.console.print("[red]Please load a file or set code first[/red]")
            return False

        return True


def start_repl() -> None:
    """Start the Tree-sitter debug REPL."""
    repl = DebugREPL()
    repl.start()
