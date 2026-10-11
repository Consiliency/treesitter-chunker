"""Kotlin signature metadata extraction (treesitter-chunker#354)."""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .signature_only import SignatureOnlyMetadataExtractor


class KotlinMetadataExtractor(SignatureOnlyMetadataExtractor):
    """Signatures for Kotlin functions."""

    def __init__(self, language: str = "kotlin"):
        """Initialize the Kotlin metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract a function signature.

        Parameters keep their declared text (``id: String``, ``vararg xs: T``,
        ``a: Int = 1``). The return type is the declared ``: Type``; a function
        without one has ``None``. An extension function's receiver type is
        reported as ``receiver``.
        """
        if node.type != "function_declaration":
            return None
        name = self._text(self._find_child_by_type(node, "simple_identifier"), source)
        if not name:
            return None

        params_node = self._find_child_by_type(node, "function_value_parameters")
        parameters = (
            self._group_parameters(params_node.children, source) if params_node else []
        )

        return_type = None
        if params_node is not None:
            return_node = self._named_child_after(node, ":", params_node.end_byte)
            if return_node is not None and return_node.type not in {
                "function_body",
                "type_constraints",
            }:
                return_type = self._text(return_node, source)

        receiver_node = node.child_by_field_name("receiver")
        if receiver_node is None:
            receiver_node = self._find_child_by_type(node, "receiver_type")
        receiver = self._text(receiver_node, source)

        decorators: list[str] = []
        modifiers: list[str] = []
        modifiers_node = self._find_child_by_type(node, "modifiers")
        if modifiers_node is not None:
            for child in modifiers_node.named_children:
                text = self._text(child, source)
                if not text:
                    continue
                if child.type == "annotation":
                    decorators.append(text)
                else:
                    modifiers.append(text)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
            receiver=receiver,
        )
