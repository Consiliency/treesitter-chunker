"""Ruby signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor


class RubyMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for Ruby methods and singleton methods."""

    def __init__(self, language: str = "ruby"):
        """Initialize the Ruby metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a method or singleton method signature.

        Parameters keep their declared text (``b = 1``, ``*rest``, ``c:``,
        ``**opts``, ``&blk``), with or without parentheses in the source.
        Ruby declares no return type. A singleton method's object (``self``
        in ``def self.make``) is reported as ``receiver``.
        """
        if node.type not in {"method", "singleton_method"}:
            return None
        name = self._text(node.child_by_field_name("name"), source)
        if not name:
            return None

        params_node = node.child_by_field_name("parameters")
        parameters = (
            self._group_parameters(params_node.children, source) if params_node else []
        )

        receiver = None
        if node.type == "singleton_method":
            receiver = self._text(node.child_by_field_name("object"), source)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=None,
            decorators=[],
            modifiers=[],
            receiver=receiver,
        )
