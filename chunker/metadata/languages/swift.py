"""Swift signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor

_EFFECT_TOKENS = frozenset({"async", "throws", "rethrows"})


class SwiftMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for Swift functions and protocol requirements."""

    def __init__(self, language: str = "swift"):
        """Initialize the Swift metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a function or protocol function signature.

        Parameters keep their declared text, including argument labels and
        defaults (``with b: inout [String: Int]``). The return type is the
        type after ``->``; a function without one has ``None``. ``async`` and
        ``throws`` are reported as modifiers.
        """
        if node.type not in {"function_declaration", "protocol_function_declaration"}:
            return None
        name = self._text(node.child_by_field_name("name"), source)
        if not name:
            return None

        param_children = self._parenthesized_children(node)
        parameters = (
            self._group_parameters(param_children, source) if param_children else []
        )

        body = node.child_by_field_name("body")
        return_node = self._named_child_after(node, "->")
        if body is not None and return_node is not None:
            if return_node.start_byte >= body.start_byte:
                return_node = None
        return_type = self._text(return_node, source)

        decorators: list[str] = []
        modifiers: list[str] = []
        modifiers_node = self._find_child_by_type(node, "modifiers")
        if modifiers_node is not None:
            for child in modifiers_node.named_children:
                text = self._text(child, source)
                if not text:
                    continue
                if child.type == "attribute":
                    decorators.append(text)
                else:
                    modifiers.append(text)
        for child in node.children:
            if child.type in _EFFECT_TOKENS and (
                body is None or child.start_byte < body.start_byte
            ):
                modifiers.append(child.type)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )
