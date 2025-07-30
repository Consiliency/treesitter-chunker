"""
Interactive AST node explorer for Tree-sitter.
"""

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree as RichTree
from tree_sitter import Node, Tree

from chunker.parser import get_parser


@dataclass
class NodeInfo:
    """Detailed information about a Tree-sitter node."""

    node: Node
    path: list[int]  # Path from root
    depth: int
    parent: Node | None
    siblings: list[Node]
    content: str

    @property
    def breadcrumb(self) -> str:
        """Get breadcrumb path to node."""
        return " > ".join(str(i) for i in self.path)


class NodeExplorer:
    """Interactive explorer for Tree-sitter AST nodes."""

    def __init__(self, language: str):
        """Initialize explorer."""
        self.language = language
        self.parser = get_parser(language)
        self.console = Console()
        self.current_node: Node | None = None
        self.current_tree: Tree | None = None
        self.current_content: str = ""
        self.node_history: list[NodeInfo] = []
        self.bookmarks: dict[str, NodeInfo] = {}

    def explore_file(self, file_path: str) -> None:
        """Start exploring a file's AST."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        self.explore_code(content)

    def explore_code(self, source_code: str) -> None:
        """Start exploring source code AST."""
        self.current_content = source_code
        self.current_tree = self.parser.parse(source_code.encode())
        self.current_node = self.current_tree.root_node
        self.node_history = []

        self.console.print(
            Panel(
                "[bold]AST Node Explorer[/bold]\n"
                "Commands: help, up, down <n>, child <n>, parent, "
                "siblings, info, tree, find <type>, bookmark <name>, quit",
                expand=False,
            ),
        )

        self._interactive_loop()

    def _interactive_loop(self) -> None:
        """Main interactive exploration loop."""
        while True:
            # Display current node
            self._display_current_node()

            # Get command
            try:
                command = Prompt.ask("\n[cyan]explorer>[/cyan]").strip()

                if not command:
                    continue

                parts = command.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                # Execute command
                if cmd in ["q", "quit", "exit"]:
                    break
                if cmd == "help":
                    self._show_help()
                elif cmd == "up":
                    self._go_up()
                elif cmd == "down":
                    self._go_down(args)
                elif cmd == "child":
                    self._go_to_child(args)
                elif cmd == "parent":
                    self._go_to_parent()
                elif cmd == "siblings":
                    self._show_siblings()
                elif cmd == "info":
                    self._show_detailed_info()
                elif cmd == "tree":
                    self._show_subtree()
                elif cmd == "find":
                    self._find_nodes(args)
                elif cmd == "bookmark":
                    self._bookmark_node(args)
                elif cmd == "bookmarks":
                    self._list_bookmarks()
                elif cmd == "goto":
                    self._goto_bookmark(args)
                elif cmd == "history":
                    self._show_history()
                elif cmd == "back":
                    self._go_back()
                elif cmd == "source":
                    self._show_source()
                elif cmd == "query":
                    self._test_query(args)
                else:
                    self.console.print(f"[red]Unknown command: {cmd}[/red]")

            except KeyboardInterrupt:
                if Confirm.ask("\nExit explorer?"):
                    break
            except (IndexError, KeyError, TypeError) as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def _display_current_node(self) -> None:
        """Display current node information."""
        if not self.current_node:
            return

        # Create info panel
        info = self._get_node_info(self.current_node)

        # Basic info
        lines = [
            f"[bold]Type:[/bold] [green]{self.current_node.type}[/green]",
            f"[bold]Location:[/bold] {info.breadcrumb}",
            f"[bold]Range:[/bold] {self.current_node.start_point} → {self.current_node.end_point}",
            f"[bold]Children:[/bold] {self.current_node.child_count}",
        ]

        # Skip field name display for now

        # Show content preview
        if self.current_node.child_count == 0:
            content = info.content
            if len(content) > 100:
                content = content[:97] + "..."
            lines.append(f"[bold]Content:[/bold] {content!r}")

        panel = Panel("\n".join(lines), title="Current Node", expand=False)
        self.console.print(panel)

    def _get_node_info(self, node: Node) -> NodeInfo:
        """Get detailed info about a node."""
        # Find path to node
        path = []
        parent = None

        # This is a simplified path - in real implementation would traverse from root
        depth = 0
        temp = node
        while hasattr(temp, "parent"):
            depth += 1
            parent = temp.parent if hasattr(temp, "parent") else None
            temp = parent
            if not temp:
                break

        # Get siblings
        siblings = []
        if parent:
            siblings = list(parent.children)

        # Get content
        content = self.current_content[node.start_byte : node.end_byte]

        return NodeInfo(
            node=node,
            path=path,
            depth=depth,
            parent=parent,
            siblings=siblings,
            content=content,
        )

    def _show_help(self) -> None:
        """Show help information."""
        help_text = """
[bold]Navigation Commands:[/bold]
  up              - Move up in the tree (broader view)
  down [n]        - Move down to the nth occurrence in subtree
  child <n>       - Go to nth child (0-based)
  parent          - Go to parent node
  back            - Go to previous node in history

[bold]Information Commands:[/bold]
  info            - Show detailed node information
  siblings        - Show sibling nodes
  tree            - Show subtree structure
  source          - Show source code for node
  history         - Show navigation history

[bold]Search Commands:[/bold]
  find <type>     - Find nodes of given type
  query <query>   - Test Tree-sitter query on subtree

[bold]Bookmark Commands:[/bold]
  bookmark <name> - Bookmark current node
  bookmarks       - List all bookmarks
  goto <name>     - Go to bookmarked node

[bold]Other Commands:[/bold]
  help            - Show this help
  quit            - Exit explorer
"""
        self.console.print(Panel(help_text, title="Help", expand=False))

    def _go_to_child(self, args: str) -> None:
        """Navigate to a child node."""
        try:
            index = int(args)
            if 0 <= index < self.current_node.child_count:
                self._push_history()
                self.current_node = self.current_node.children[index]
            else:
                self.console.print(
                    f"[red]Invalid child index. Node has {self.current_node.child_count} children.[/red]",
                )
        except ValueError:
            self.console.print("[red]Please provide a child index number.[/red]")

    def _go_to_parent(self) -> None:
        """Navigate to parent node."""
        # In actual implementation, would track parent relationships
        self.console.print(
            "[yellow]Parent navigation requires tracking - going back instead[/yellow]",
        )
        self._go_back()

    def _go_up(self) -> None:
        """Move up in tree (broader view)."""
        self._go_to_parent()

    def _go_down(self, args: str) -> None:
        """Move down to first matching child."""
        if self.current_node.child_count == 0:
            self.console.print("[yellow]No children to navigate to.[/yellow]")
            return

        # If no args, go to first child
        if not args:
            self._push_history()
            self.current_node = self.current_node.children[0]
        else:
            # Find nth occurrence of any node
            try:
                int(args)
                self._push_history()
                # Simple implementation - just go to first child
                self.current_node = self.current_node.children[0]
            except ValueError:
                self.console.print("[red]Invalid number.[/red]")

    def _show_siblings(self) -> None:
        """Show sibling nodes."""
        info = self._get_node_info(self.current_node)

        if not info.siblings:
            self.console.print("[yellow]No siblings found.[/yellow]")
            return

        table = Table(title="Siblings")
        table.add_column("Index", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Field", style="yellow")
        table.add_column("Preview", style="white")

        for i, sibling in enumerate(info.siblings):
            preview = ""
            if sibling.child_count == 0:
                preview = self.current_content[sibling.start_byte : sibling.end_byte]
                if len(preview) > 40:
                    preview = preview[:37] + "..."

            table.add_row(
                str(i),
                sibling.type,
                "",  # Skip field name
                (
                    repr(preview)
                    if preview
                    else f"[dim]{sibling.child_count} children[/dim]"
                ),
            )

        self.console.print(table)

    def _show_detailed_info(self) -> None:
        """Show detailed node information."""
        node = self.current_node
        self._get_node_info(node)

        details = {
            "Type": node.type,
            "Start Point": f"{node.start_point[0]}:{node.start_point[1]}",
            "End Point": f"{node.end_point[0]}:{node.end_point[1]}",
            "Start Byte": str(node.start_byte),
            "End Byte": str(node.end_byte),
            "Child Count": str(node.child_count),
            "Has Error": str(node.has_error),
            "Is Missing": str(node.is_missing),
            "Is Named": str(node.is_named),
        }

        table = Table(title="Node Details", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        for key, value in details.items():
            table.add_row(key, value)

        self.console.print(table)

        # Skip field display for now

    def _show_subtree(self) -> None:
        """Show subtree structure."""
        tree = RichTree(
            f"[green]{self.current_node.type}[/green]",
        )

        def add_children(node: Node, tree_node: RichTree, depth: int = 0):
            if depth > 3:  # Limit depth
                if node.child_count > 0:
                    tree_node.add("[dim]...[/dim]")
                return

            for child in node.children:
                label = f"[green]{child.type}[/green]"
                # Skip field name
                if child.child_count == 0:
                    text = self.current_content[child.start_byte : child.end_byte]
                    if len(text) > 30:
                        text = text[:27] + "..."
                    label += f' [cyan]"{text}"[/cyan]'

                child_tree = tree_node.add(label)
                add_children(child, child_tree, depth + 1)

        add_children(self.current_node, tree)
        self.console.print(tree)

    def _find_nodes(self, node_type: str) -> None:
        """Find nodes of a given type in subtree."""
        if not node_type:
            self.console.print("[red]Please specify a node type to find.[/red]")
            return

        found = []

        def search(node: Node, path: list[int]):
            if node.type == node_type:
                found.append((node, path.copy()))
            for i, child in enumerate(node.children):
                search(child, [*path, i])

        search(self.current_node, [])

        if not found:
            self.console.print(
                f"[yellow]No nodes of type '{node_type}' found.[/yellow]",
            )
            return

        table = Table(title=f"Found {len(found)} nodes of type '{node_type}'")
        table.add_column("Path", style="cyan")
        table.add_column("Location", style="green")
        table.add_column("Preview", style="white")

        for node, path in found[:10]:  # Limit display
            preview = ""
            if node.child_count == 0:
                preview = self.current_content[node.start_byte : node.end_byte]
                if len(preview) > 40:
                    preview = preview[:37] + "..."

            table.add_row(
                ".".join(map(str, path)),
                f"{node.start_point[0]}:{node.start_point[1]}",
                repr(preview) if preview else f"[dim]{node.child_count} children[/dim]",
            )

        self.console.print(table)

    def _show_source(self) -> None:
        """Show source code for current node."""
        content = self.current_content[
            self.current_node.start_byte : self.current_node.end_byte
        ]

        syntax = Syntax(
            content,
            self.language,
            theme="monokai",
            line_numbers=True,
            start_line=self.current_node.start_point[0] + 1,
        )

        self.console.print(
            Panel(syntax, title=f"Source: {self.current_node.type}", expand=False),
        )

    def _push_history(self) -> None:
        """Push current node to history."""
        if self.current_node:
            info = self._get_node_info(self.current_node)
            self.node_history.append(info)

    def _go_back(self) -> None:
        """Go back in history."""
        if not self.node_history:
            self.console.print("[yellow]No history to go back to.[/yellow]")
            return

        info = self.node_history.pop()
        self.current_node = info.node

    def _show_history(self) -> None:
        """Show navigation history."""
        if not self.node_history:
            self.console.print("[yellow]No navigation history.[/yellow]")
            return

        table = Table(title="Navigation History")
        table.add_column("Step", style="cyan")
        table.add_column("Node Type", style="green")
        table.add_column("Location", style="white")

        for i, info in enumerate(self.node_history[-10:]):  # Last 10
            table.add_row(
                str(i + 1),
                info.node.type,
                f"{info.node.start_point[0]}:{info.node.start_point[1]}",
            )

        self.console.print(table)

    def _bookmark_node(self, name: str) -> None:
        """Bookmark current node."""
        if not name:
            self.console.print("[red]Please provide a bookmark name.[/red]")
            return

        info = self._get_node_info(self.current_node)
        self.bookmarks[name] = info
        self.console.print(f"[green]Bookmarked current node as '{name}'[/green]")

    def _list_bookmarks(self) -> None:
        """List all bookmarks."""
        if not self.bookmarks:
            self.console.print("[yellow]No bookmarks set.[/yellow]")
            return

        table = Table(title="Bookmarks")
        table.add_column("Name", style="cyan")
        table.add_column("Node Type", style="green")
        table.add_column("Location", style="white")

        for name, info in self.bookmarks.items():
            table.add_row(
                name,
                info.node.type,
                f"{info.node.start_point[0]}:{info.node.start_point[1]}",
            )

        self.console.print(table)

    def _goto_bookmark(self, name: str) -> None:
        """Go to bookmarked node."""
        if not name:
            self.console.print("[red]Please provide a bookmark name.[/red]")
            return

        if name not in self.bookmarks:
            self.console.print(f"[red]Bookmark '{name}' not found.[/red]")
            return

        self._push_history()
        info = self.bookmarks[name]
        self.current_node = info.node
        self.console.print(f"[green]Jumped to bookmark '{name}'[/green]")

    def _test_query(self, query_string: str) -> None:
        """Test a Tree-sitter query on current subtree."""
        if not query_string:
            self.console.print("[red]Please provide a query string.[/red]")
            return

        try:
            from chunker.debug.interactive.query_debugger import debug_query

            # Get subtree content
            subtree_content = self.current_content[
                self.current_node.start_byte : self.current_node.end_byte
            ]

            # Run query
            matches = debug_query(
                query_string,
                subtree_content,
                self.language,
                show_ast=False,
                show_captures=True,
            )

            self.console.print(
                f"[green]Found {len(matches)} matches in subtree[/green]",
            )

        except (IndexError, KeyError, TypeError) as e:
            self.console.print(f"[red]Query error: {e}[/red]")


def explore_ast(
    source_code: str,
    language: str,
) -> None:
    """
    Quick function to explore an AST interactively.

    Args:
        source_code: Code to parse
        language: Programming language
    """
    explorer = NodeExplorer(language)
    explorer.explore_code(source_code)
