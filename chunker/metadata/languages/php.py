"""PHP signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor

_MODIFIER_TYPES = frozenset(
    {
        "visibility_modifier",
        "static_modifier",
        "abstract_modifier",
        "final_modifier",
        "readonly_modifier",
    },
)


class PhpMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for PHP methods and functions."""

    def __init__(self, language: str = "php"):
        """Initialize the PHP metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a method or function signature.

        Parameters keep their declared text (``?string $id``,
        ``array &$opts = []``, ``int ...$rest``). The return type is the
        declared ``: type``; attributes are reported as decorators.
        """
        if node.type not in {"method_declaration", "function_definition"}:
            return None
        name = self._text(node.child_by_field_name("name"), source)
        if not name:
            return None

        params_node = node.child_by_field_name("parameters")
        parameters = (
            self._group_parameters(params_node.children, source) if params_node else []
        )

        return_type = self._text(node.child_by_field_name("return_type"), source)

        decorators: list[str] = []
        attributes = self._text(node.child_by_field_name("attributes"), source)
        if attributes:
            decorators.append(attributes)
        modifiers = [
            text
            for child in node.children
            if child.type in _MODIFIER_TYPES
            for text in [self._text(child, source)]
            if text
        ]

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )
