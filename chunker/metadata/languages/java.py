"""Java signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor

_ANNOTATION_TYPES = frozenset({"annotation", "marker_annotation"})


class JavaMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for Java methods and constructors."""

    def __init__(self, language: str = "java"):
        """Initialize the Java metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a method or constructor signature.

        Parameters keep their declared text (``final String id``,
        ``String... rest``). A method's return type is its declared type,
        including ``void``; constructors have none.
        """
        if node.type not in {"method_declaration", "constructor_declaration"}:
            return None
        name = self._text(node.child_by_field_name("name"), source)
        if not name:
            return None

        params_node = node.child_by_field_name("parameters")
        parameters = (
            self._group_parameters(params_node.children, source) if params_node else []
        )

        return_type = None
        if node.type == "method_declaration":
            return_type = self._text(node.child_by_field_name("type"), source)

        decorators: list[str] = []
        modifiers: list[str] = []
        modifiers_node = self._find_child_by_type(node, "modifiers")
        if modifiers_node is not None:
            for child in modifiers_node.children:
                text = self._text(child, source)
                if not text:
                    continue
                if child.type in _ANNOTATION_TYPES:
                    decorators.append(text)
                else:
                    modifiers.append(text)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )
