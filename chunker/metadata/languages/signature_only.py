"""Shared base for extractors that only provide signature metadata.

Java, C#, Kotlin, Swift, PHP and Ruby register these extractors so their
method and function chunks carry ``signature`` metadata
(treesitter-chunker#354). Docstrings, imports, exports, dependencies and calls
stay empty for these languages, as they were before an extractor existed.
"""

from typing import Any

from tree_sitter import Node

from chunker.metadata.extractor import BaseMetadataExtractor


class SignatureOnlyMetadataExtractor(BaseMetadataExtractor):
    """Base extractor whose only populated field is the signature."""

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Docstrings are not extracted for this language."""
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Imports are not extracted for this language."""
        return []

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Dependencies are not extracted for this language."""
        return set()

    def extract_exports(self, node: Node, source: bytes) -> set[str]:
        """Exports are not extracted for this language."""
        return set()

    def extract_calls(self, node: Node, source: bytes) -> list[dict[str, Any]]:
        """Calls are not extracted for this language."""
        return []

    def _text(self, node: Node | None, source: bytes) -> str | None:
        """Return a node's stripped source text, or ``None``."""
        if node is None:
            return None
        return self._get_node_text(node, source).strip() or None

    def _group_parameters(self, children: list[Node], source: bytes) -> list[Any]:
        """Return each comma-separated parameter's source text.

        ``children`` are the nodes of one parameter list. Parentheses, commas
        and comments delimit parameters; each parameter's text spans its first
        to last node, so modifiers and defaults that the grammar places beside
        the parameter node (C# ``params``, Kotlin ``vararg``, Swift defaults)
        stay with it.
        """
        parameters: list[Any] = []
        group: list[Node] = []

        def flush() -> None:
            if group:
                text = source[group[0].start_byte : group[-1].end_byte].decode(
                    "utf-8",
                )
                parameters.append(text.strip())
                group.clear()

        for child in children:
            if child.type == ",":
                flush()
            elif child.type in {"(", ")"} or "comment" in child.type:
                continue
            else:
                group.append(child)
        flush()
        return [parameter for parameter in parameters if parameter]

    def _parenthesized_children(self, node: Node) -> list[Node] | None:
        """Return the direct children between ``node``'s first ``(`` and ``)``."""
        children = node.children
        open_index = next(
            (i for i, child in enumerate(children) if child.type == "("),
            None,
        )
        if open_index is None:
            return None
        close_index = next(
            (
                i
                for i in range(open_index + 1, len(children))
                if children[i].type == ")"
            ),
            None,
        )
        if close_index is None:
            return None
        return children[open_index + 1 : close_index]

    def _named_child_after(
        self,
        node: Node,
        token: str,
        start_byte: int = 0,
    ) -> Node | None:
        """Return the first named child after an unnamed ``token`` child."""
        seen = False
        for child in node.children:
            if child.start_byte < start_byte:
                continue
            if seen and child.is_named and "comment" not in child.type:
                return child
            if not child.is_named and child.type == token:
                seen = True
        return None
