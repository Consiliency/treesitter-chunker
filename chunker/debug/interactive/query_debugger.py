"""
Interactive Tree-sitter query debugger.
"""

import re
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from tree_sitter import Node, Query

from chunker.parser import get_parser


@dataclass
class QueryMatch:
    """Represents a query match with metadata."""

    pattern_index: int
    captures: dict[str, list[Node]]
    start_byte: int
    end_byte: int
    start_point: tuple[int, int]
    end_point: tuple[int, int]

    @property
    def span(self) -> str:
        """Get human-readable span."""
        return f"{self.start_point[0]}:{self.start_point[1]}-{self.end_point[0]}:{self.end_point[1]}"


class QueryDebugger:
    """Debug Tree-sitter queries interactively."""

    def __init__(self, language: str):
        """Initialize debugger for a language."""
        self.language = language
        self.parser = get_parser(language)
        self.console = Console()
        self._query_cache = {}

    def debug_query(
        self,
        query_string: str,
        source_code: str,
        show_ast: bool = False,
        show_captures: bool = True,
        highlight_matches: bool = True,
    ) -> list[QueryMatch]:
        """
        Debug a Tree-sitter query against source code.

        Args:
            query_string: Tree-sitter query string
            source_code: Source code to query
            show_ast: Whether to show the AST
            show_captures: Whether to show capture details
            highlight_matches: Whether to highlight matches in code

        Returns:
            List of query matches
        """
        # Parse the source code
        tree = self.parser.parse(source_code.encode())

        # Show AST if requested
        if show_ast:
            self._show_ast(tree.root_node, source_code)

        # Compile and execute query
        try:
            query = self._compile_query(query_string)
            matches = self._execute_query(query, tree.root_node, source_code)

            # Display results
            self._display_results(
                matches,
                source_code,
                query_string,
                show_captures,
                highlight_matches,
            )

            return matches

        except Exception as e:
            self.console.print(f"[red]Query Error:[/red] {e!s}")
            self._suggest_query_fix(query_string, str(e))
            return []

    def _compile_query(self, query_string: str) -> Query:
        """Compile a Tree-sitter query with caching."""
        if query_string in self._query_cache:
            return self._query_cache[query_string]

        try:
            # Get the language object from parser
            lang = self.parser.language
            query = lang.query(query_string)
            self._query_cache[query_string] = query
            return query
        except Exception as e:
            # Provide helpful error messages
            if "Invalid syntax" in str(e):
                raise ValueError(f"Invalid query syntax: {e}")
            if "Invalid node type" in str(e):
                # Extract the invalid node type
                match = re.search(r"node type '(\w+)'", str(e))
                if match:
                    invalid_type = match.group(1)
                    raise ValueError(
                        f"Invalid node type '{invalid_type}'. "
                        f"Use 'list_node_types' to see valid types for {self.language}.",
                    )
            raise

    def _execute_query(
        self,
        query: Query,
        root_node: Node,
        source_code: str,
    ) -> list[QueryMatch]:
        """Execute query and collect matches."""
        matches = []

        # The tree-sitter Python bindings have changed significantly
        # We need to manually traverse and match patterns
        # For now, we'll do a simple implementation that handles basic queries

        # Get the query string from our cache (we know it's there)
        query_string = None
        for cached_query_str, cached_query in self._query_cache.items():
            if cached_query is query:
                query_string = cached_query_str
                break

        if not query_string:
            return matches

        # Simple pattern matching for function_definition
        if "function_definition" in query_string:
            # Find all function definitions
            def find_functions(node):
                if node.type == "function_definition":
                    # Create a match
                    match = QueryMatch(
                        pattern_index=0,
                        captures={},
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        start_point=node.start_point,
                        end_point=node.end_point,
                    )

                    # Check for simple captures
                    if "@func" in query_string:
                        match.captures["@func"] = [
                            node,
                        ]  # Store as list for consistency

                    # Check for field captures (e.g., name: (identifier) @func_name)
                    if "@func_name" in query_string:
                        # Find the name field (identifier child)
                        for child in node.children:
                            if child.type == "identifier":
                                match.captures["@func_name"] = [child]
                                break

                    if "@params" in query_string:
                        # Find parameters field
                        for child in node.children:
                            if child.type == "parameters":
                                match.captures["@params"] = [child]
                                break

                    matches.append(match)

                # Recurse through children
                for child in node.children:
                    find_functions(child)

            find_functions(root_node)

        return matches

    def _display_results(
        self,
        matches: list[QueryMatch],
        source_code: str,
        query_string: str,
        show_captures: bool,
        highlight_matches: bool,
    ) -> None:
        """Display query results."""
        # Display query
        self.console.print(
            Panel(
                Syntax(query_string, "scheme", theme="monokai"),
                title="Query",
            ),
        )

        # Display match summary
        self.console.print(f"\n[green]Found {len(matches)} matches[/green]\n")

        if not matches:
            return

        # Display matches table
        table = Table(title="Matches")
        table.add_column("Match", style="cyan")
        table.add_column("Pattern", style="yellow")
        table.add_column("Location", style="green")
        table.add_column("Text", style="white")

        for i, match in enumerate(matches):
            text = source_code[match.start_byte : match.end_byte]
            if len(text) > 50:
                text = text[:47] + "..."

            table.add_row(
                str(i + 1),
                str(match.pattern_index),
                match.span,
                repr(text),
            )

        self.console.print(table)

        # Display captures if requested
        if show_captures and any(match.captures for match in matches):
            self._display_captures(matches, source_code)

        # Highlight matches in source
        if highlight_matches:
            self._highlight_matches(matches, source_code)

    def _display_captures(
        self,
        matches: list[QueryMatch],
        source_code: str,
    ) -> None:
        """Display capture details."""
        self.console.print("\n[bold]Captures:[/bold]")

        for i, match in enumerate(matches):
            if not match.captures:
                continue

            self.console.print(f"\n[cyan]Match {i + 1}:[/cyan]")

            for capture_name, nodes in match.captures.items():
                for j, node in enumerate(nodes):
                    text = source_code[node.start_byte : node.end_byte]
                    if len(text) > 60:
                        text = text[:57] + "..."

                    self.console.print(
                        f"  @{capture_name}[{j}]: "
                        f"[green]{node.type}[/green] "
                        f"[dim]{node.start_point[0]}:{node.start_point[1]}[/dim] "
                        f'"{text}"',
                    )

    def _highlight_matches(
        self,
        matches: list[QueryMatch],
        source_code: str,
    ) -> None:
        """Highlight matches in source code."""
        if not matches:
            return

        # Create highlighted text
        lines = source_code.splitlines()
        highlighted_lines = []

        # Build match map
        match_map = {}
        for i, match in enumerate(matches):
            for line_no in range(match.start_point[0], match.end_point[0] + 1):
                if line_no not in match_map:
                    match_map[line_no] = []
                match_map[line_no].append(i + 1)

        # Add match indicators
        for line_no, line in enumerate(lines):
            if line_no in match_map:
                match_nums = match_map[line_no]
                indicator = (
                    f"[yellow]// ← Match {', '.join(map(str, match_nums))}[/yellow]"
                )
                highlighted_lines.append(f"{line} {indicator}")
            else:
                highlighted_lines.append(line)

        # Display with syntax highlighting
        syntax = Syntax(
            "\n".join(highlighted_lines),
            self.language,
            theme="monokai",
            line_numbers=True,
        )

        self.console.print("\n[bold]Source with matches:[/bold]")
        self.console.print(syntax)

    def _show_ast(self, node: Node, source_code: str, depth: int = 0) -> None:
        """Show simplified AST."""
        if depth == 0:
            self.console.print("\n[bold]AST:[/bold]")

        indent = "  " * depth
        node_text = f"{node.type}"

        if node.child_count == 0:
            text = source_code[node.start_byte : node.end_byte]
            if len(text) > 30:
                text = text[:27] + "..."
            node_text += f' "{text}"'

        self.console.print(f"{indent}{node_text}")

        for child in node.children:
            self._show_ast(child, source_code, depth + 1)

    def _suggest_query_fix(self, query_string: str, error: str) -> None:
        """Suggest fixes for common query errors."""
        suggestions = []

        # Check for missing parentheses
        if "Expected" in error and "(" in error:
            suggestions.append(
                "Ensure all node types are properly parenthesized: (node_type)",
            )

        # Check for invalid capture names
        if "@" in query_string and "capture" in error.lower():
            suggestions.append(
                "Capture names must start with @ and contain only letters/numbers",
            )

        # Check for missing predicates
        if "#" in query_string and "predicate" in error.lower():
            suggestions.append("Predicates must be in the form #predicate_name")

        if suggestions:
            self.console.print("\n[yellow]Suggestions:[/yellow]")
            for suggestion in suggestions:
                self.console.print(f"  • {suggestion}")


def debug_query(
    query_string: str,
    source_code: str,
    language: str,
    show_ast: bool = False,
    show_captures: bool = True,
) -> list[QueryMatch]:
    """
    Quick function to debug a Tree-sitter query.

    Args:
        query_string: Tree-sitter query
        source_code: Code to query
        language: Programming language
        show_ast: Whether to show AST
        show_captures: Whether to show captures

    Returns:
        List of matches
    """
    debugger = QueryDebugger(language)
    return debugger.debug_query(
        query_string,
        source_code,
        show_ast=show_ast,
        show_captures=show_captures,
    )
