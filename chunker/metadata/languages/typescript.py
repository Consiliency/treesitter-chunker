"""TypeScript-specific metadata extraction.

This module extends the JavaScript extractor to handle TypeScript-specific features.
"""

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo

from .javascript import JavaScriptComplexityAnalyzer, JavaScriptMetadataExtractor


class TypeScriptMetadataExtractor(JavaScriptMetadataExtractor):
    """TypeScript-specific metadata extraction implementation."""

    def __init__(self, language: str = "typescript"):
        """Initialize the TypeScript metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function/method signature information with TypeScript-specific handling."""
        base_signature = super().extract_signature(node, source)
        if not base_signature:
            return None
        if node.type == "method_signature":
            name_node = self._find_child_by_type(node, "property_identifier")
            if not name_node:
                name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                base_signature.name = self._get_node_text(name_node, source)
            if "interface_method" not in base_signature.modifiers:
                base_signature.modifiers.append("interface_method")
        if (
            self._is_abstract_method(
                node,
                source,
            )
            and "abstract" not in base_signature.modifiers
        ):
            base_signature.modifiers.append("abstract")
        if (
            self._is_overload_signature(
                node,
                source,
            )
            and "overload" not in base_signature.modifiers
        ):
            base_signature.modifiers.append("overload")
        return base_signature

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract dependencies with TypeScript type imports."""
        dependencies = super().extract_dependencies(node, source)
        type_imports = self._extract_type_imports(node, source)
        dependencies.update(type_imports)
        type_refs = self._extract_type_references(node, source)
        dependencies.update(type_refs)
        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> set[str]:
        """Extract exports including TypeScript-specific exports."""
        exports = super().extract_exports(node, source)
        if node.type in {"interface_declaration", "type_alias_declaration"}:
            name_node = self._find_child_by_type(node, "type_identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))
        elif node.type == "enum_declaration":
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))
        return exports

    @staticmethod
    def _is_abstract_method(node: Node, _source: bytes) -> bool:
        """Check if method is abstract."""
        if node.parent:
            for sibling in node.parent.children:
                if sibling.type == "abstract" and sibling.end_byte <= node.start_byte:
                    return True
        return False

    def _is_overload_signature(self, node: Node, _source: bytes) -> bool:
        """Check if this is a function overload signature."""
        return node.type == "function_signature" or (
            node.type == "method_signature"
            and not self._find_child_by_type(node, "statement_block")
        )

    def _extract_type_imports(self, node: Node, source: bytes) -> set[str]:
        """Extract type-only imports."""
        type_imports = set()

        def collect_type_imports(n: Node, _depth: int):
            if n.type == "import_statement":
                self._process_type_import(n, source, type_imports)

        self._walk_tree(node, collect_type_imports)
        return type_imports

    def _process_type_import(self, node: Node, source: bytes, type_imports: set[str]):
        """Process a potential type import statement."""
        text = self._get_node_text(node, source)
        if "import type" not in text:
            return

        import_clause = self._find_child_by_type(node, "import_clause")
        if not import_clause:
            return

        named_imports = self._find_child_by_type(import_clause, "named_imports")
        if not named_imports:
            return

        self._extract_named_type_imports(named_imports, source, type_imports)

    def _extract_named_type_imports(
        self,
        named_imports: Node,
        source: bytes,
        type_imports: set[str],
    ):
        """Extract individual type imports from named imports."""
        for child in named_imports.children:
            if child.type != "import_specifier":
                continue

            id_node = self._find_child_by_type(child, "identifier")
            if id_node:
                type_imports.add(self._get_node_text(id_node, source))

    def _extract_type_references(self, node: Node, source: bytes) -> set[str]:
        """Extract referenced type names."""
        type_refs = set()

        def collect_type_refs(n: Node, _depth: int):
            if n.type == "type_identifier":
                type_refs.add(self._get_node_text(n, source))
            elif n.type == "generic_type":
                type_id = self._find_child_by_type(n, "type_identifier")
                if type_id:
                    type_refs.add(self._get_node_text(type_id, source))

        self._walk_tree(node, collect_type_refs)
        return type_refs


class TypeScriptComplexityAnalyzer(JavaScriptComplexityAnalyzer):
    """TypeScript-specific complexity analysis."""

    def __init__(self):
        """Initialize with TypeScript language."""
        super(JavaScriptComplexityAnalyzer, self).__init__("typescript")
        self._decision_points = self._get_decision_point_types()
        self._cognitive_factors = self._get_cognitive_complexity_factors()

    def _get_decision_point_types(self) -> set[str]:
        """Get TypeScript-specific decision point types."""
        js_points = super()._get_decision_point_types()
        ts_specific = {"as_expression", "satisfies_expression", "non_null_expression"}
        return js_points.union(ts_specific)

    def _get_cognitive_complexity_factors(self) -> dict[str, int]:
        """Get TypeScript-specific cognitive complexity factors."""
        js_factors = super()._get_cognitive_complexity_factors()
        ts_specific = {
            "as_expression": 0,
            "satisfies_expression": 0,
            "non_null_expression": 1,
            "type_predicate": 1,
        }
        return {**js_factors, **ts_specific}
