"""Python-specific context extraction implementation."""

from tree_sitter import Node

from chunker.context.extractor import BaseContextExtractor
from chunker.context.filter import BaseContextFilter
from chunker.context.scope_analyzer import BaseScopeAnalyzer
from chunker.context.symbol_resolver import BaseSymbolResolver
from chunker.interfaces.context import ContextItem, ContextType


class PythonContextExtractor(BaseContextExtractor):
    """Python-specific context extraction."""

    def __init__(self):
        """Initialize Python context extractor."""
        super().__init__("python")

    @staticmethod
    def _is_import_node(node: Node) -> bool:
        """Check if a node represents an import statement."""
        return node.type in {"import_statement", "import_from_statement"}

    @staticmethod
    def _is_type_definition_node(node: Node) -> bool:
        """Check if a node represents a type definition."""
        return node.type in {"class_definition", "type_alias"}

    @staticmethod
    def _is_scope_node(node: Node) -> bool:
        """Check if a node represents a scope."""
        return node.type in {"function_definition", "class_definition", "module"}

    @staticmethod
    def _is_decorator_node(node: Node) -> bool:
        """Check if a node represents a decorator."""
        return node.type == "decorator"

    @staticmethod
    def _extract_type_declaration(node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a type definition."""
        if node.type == "class_definition":
            for child in node.children:
                if child.type == "block":
                    declaration = (
                        source[node.start_byte : child.start_byte]
                        .decode("utf-8")
                        .strip()
                    )
                    return declaration + " ..."
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()
        if node.type == "type_alias":
            return source[node.start_byte : node.end_byte].decode("utf-8").strip()
        return None

    def _extract_scope_declaration(self, node: Node, source: bytes) -> str | None:
        """Extract just the declaration part of a scope."""
        if node.type == "function_definition":
            for child in node.children:
                if child.type == ":":
                    declaration = (
                        source[node.start_byte : child.end_byte].decode("utf-8").strip()
                    )
                    return declaration
            return (
                source[node.start_byte : node.end_byte].decode("utf-8").split("\n")[0]
            )
        if node.type == "class_definition":
            return self._extract_type_declaration(node, source)
        return None

    def _find_references_in_node(
        self,
        node: Node,
        source: bytes,
    ) -> list[tuple[str, Node]]:
        """Find all identifier references in a node."""
        references = []

        def find_identifiers(n: Node):
            if n.type == "identifier":
                parent = n.parent
                if parent and not self._is_definition_context(n):
                    name = source[n.start_byte : n.end_byte].decode("utf-8")
                    references.append((name, n))
            elif n.type == "attribute":
                for child in n.children:
                    if child.type == "identifier":
                        name = source[child.start_byte : child.end_byte].decode("utf-8")
                        references.append((name, child))
                        break
            for child in n.children:
                find_identifiers(child)

        find_identifiers(node)
        return references

    @staticmethod
    def _is_definition_context(identifier_node: Node) -> bool:
        """Check if an identifier is in a definition context."""
        parent = identifier_node.parent
        if not parent:
            return False
        if parent.type in {"function_definition", "class_definition"}:
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type in {"identifier", "block", "parameters"}:
                    break
        if parent.type == "assignment":
            for child in parent.children:
                if child == identifier_node:
                    return True
                if child.type == "=":
                    break
        if parent.type in {
            "parameters",
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
            "identifier",
        }:
            return True
        return bool(
            parent.type in {"aliased_import", "dotted_name"}
            and parent.parent
            and parent.parent.type in {"import_statement", "import_from_statement"},
        )

        # Import aliases
        return bool(
            parent.type in {"aliased_import", "dotted_name"}
            and parent.parent
            and parent.parent.type in {"import_statement", "import_from_statement"},
        )

    def _find_definition(
        self,
        name: str,
        _scope_node: Node,
        ast: Node,
        source: bytes,
    ) -> ContextItem | None:
        """Find the definition of a name."""

        def find_definition(node: Node, target_name: str) -> Node | None:
            if node.type in {"class_definition", "function_definition"}:
                for child in node.children:
                    if (
                        child.type == "identifier"
                        and child.text.decode(
                            "utf-8",
                        )
                        == target_name
                    ):
                        return node
            elif node.type == "assignment":
                for child in node.children:
                    if child.type == "=":
                        break
                    if (
                        child.type == "identifier"
                        and child.text.decode(
                            "utf-8",
                        )
                        == target_name
                    ):
                        return node
            for child in node.children:
                result = find_definition(child, target_name)
                if result:
                    return result
            return None

        def_node = find_definition(ast, name)
        if def_node:
            content = source[def_node.start_byte : def_node.end_byte].decode("utf-8")
            line_number = source[: def_node.start_byte].count(b"\n") + 1
            context_type = ContextType.DEPENDENCY
            if def_node.type == "class_definition":
                context_type = ContextType.TYPE_DEF
                content = self._extract_type_declaration(def_node, source)
            elif def_node.type == "function_definition":
                content = self._extract_scope_declaration(def_node, source)
            return ContextItem(
                type=context_type,
                content=content,
                node=def_node,
                line_number=line_number,
                importance=60,
            )
        return None


class PythonSymbolResolver(BaseSymbolResolver):
    """Python-specific symbol resolution."""

    def __init__(self):
        """Initialize Python symbol resolver."""
        super().__init__("python")

    @staticmethod
    def _get_node_type_map() -> dict[str, str]:
        """Get mapping from AST node types to symbol types."""
        return {
            "function_definition": "function",
            "class_definition": "class",
            "assignment": "variable",
            "typed_parameter": "parameter",
            "default_parameter": "parameter",
            "identifier": "variable",
            "import_statement": "import",
            "import_from_statement": "import",
        }

    @staticmethod
    def _is_identifier_node(node: Node) -> bool:
        """Check if a node is an identifier."""
        return node.type == "identifier"

    @staticmethod
    def _is_definition_node(node: Node) -> bool:
        """Check if a node defines a symbol."""
        return node.type in {
            "function_definition",
            "class_definition",
            "assignment",
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        }

    @classmethod
    def _is_definition_context(cls, node: Node) -> bool:
        """Check if an identifier node is in a definition context."""
        extractor = PythonContextExtractor()
        return extractor._is_definition_context(node)

    @staticmethod
    def _get_defined_name(node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        if node.type in {"function_definition", "class_definition"}:
            for child in node.children:
                if child.type == "identifier":
                    return None
        elif node.type == "assignment":
            for child in node.children:
                if child.type == "identifier":
                    return None
                if child.type == "=":
                    break
        elif node.type in {
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        }:
            for child in node.children:
                if child.type == "identifier":
                    return None
        return None

    @staticmethod
    def _creates_new_scope(node: Node) -> bool:
        """Check if a node creates a new scope."""
        return node.type in {
            "function_definition",
            "class_definition",
            "lambda",
            "list_comprehension",
            "dictionary_comprehension",
            "set_comprehension",
            "generator_expression",
        }


class PythonScopeAnalyzer(BaseScopeAnalyzer):
    """Python-specific scope analysis."""

    def __init__(self):
        """Initialize Python scope analyzer."""
        super().__init__("python")

    @staticmethod
    def _get_scope_type_map() -> dict[str, str]:
        """Get mapping from AST node types to scope types."""
        return {
            "module": "module",
            "function_definition": "function",
            "class_definition": "class",
            "lambda": "lambda",
            "list_comprehension": "comprehension",
            "dictionary_comprehension": "comprehension",
            "set_comprehension": "comprehension",
            "generator_expression": "generator",
        }

    def _is_scope_node(self, node: Node) -> bool:
        """Check if a node creates a scope."""
        return node.type in self._get_scope_type_map()

    @classmethod
    def _is_definition_node(cls, node: Node) -> bool:
        """Check if a node defines a symbol."""
        resolver = PythonSymbolResolver()
        return resolver._is_definition_node(node)

    @staticmethod
    def _is_import_node(node: Node) -> bool:
        """Check if a node is an import statement."""
        return node.type in {"import_statement", "import_from_statement"}

    @classmethod
    def _get_defined_name(cls, node: Node) -> str | None:
        """Get the name being defined by a definition node."""
        resolver = PythonSymbolResolver()
        return resolver._get_defined_name(node)

    @staticmethod
    def _extract_imported_names(import_node: Node) -> set[str]:
        """Extract symbol names from an import node."""
        names = set()
        if import_node.type == "import_statement":
            for child in import_node.children:
                if child.type == "dotted_name":
                    pass
                elif child.type == "aliased_import":
                    for subchild in child.children:
                        if (
                            subchild.type == "identifier"
                            and subchild.prev_sibling
                            and subchild.prev_sibling.type == "as"
                        ):
                            pass
        elif import_node.type == "import_from_statement":
            for child in import_node.children:
                if (
                    child.type == "identifier"
                    and child.prev_sibling
                    and child.prev_sibling.type == "import"
                ):
                    pass
                elif child.type == "aliased_import":
                    for subchild in child.children:
                        if (
                            subchild.type == "identifier"
                            and subchild.prev_sibling
                            and subchild.prev_sibling.type == "as"
                        ):
                            pass
        return names


class PythonContextFilter(BaseContextFilter):
    """Python-specific context filtering."""

    def __init__(self):
        """Initialize Python context filter."""
        super().__init__("python")

    @staticmethod
    def _is_decorator_node(node: Node) -> bool:
        """Check if a node is a decorator."""
        return node.type == "decorator"
