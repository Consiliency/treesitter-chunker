"""C# signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor


class CSharpMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for C# methods."""

    def __init__(self, language: str = "csharp"):
        """Initialize the C# metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a method signature.

        Parameters keep their declared text, including ``ref``/``params``
        modifiers and defaults. The return type is the declared type,
        including ``void``. Attribute lists are reported as decorators.
        """
        if node.type != "method_declaration":
            return None
        name = self._text(node.child_by_field_name("name"), source)
        if not name:
            return None

        params_node = node.child_by_field_name("parameters")
        parameters = (
            self._group_parameters(params_node.children, source) if params_node else []
        )

        return_node = node.child_by_field_name("returns") or node.child_by_field_name(
            "type",
        )
        return_type = self._text(return_node, source)

        decorators: list[str] = []
        modifiers: list[str] = []
        for child in node.children:
            text = self._text(child, source)
            if not text:
                continue
            if child.type == "attribute_list":
                decorators.append(text)
            elif child.type == "modifier":
                modifiers.append(text)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )
