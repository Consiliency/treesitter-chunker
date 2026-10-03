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

    def get_visible_symbols(self, scope_node: Node, ast: Node) -> set[str]:
        """Collect lexical names without inheriting a method's class namespace."""
        visible = set()
        excluded_classes = set()
        current = scope_node
        while current:
            parent = self.get_enclosing_scope(current)
            nested_in_class = (
                parent is not None
                and parent.type == "class_definition"
                and self._is_scope_node(current)
            )
            if nested_in_class:
                excluded_classes.add(parent)
            if current in excluded_classes:
                names = set()
            elif nested_in_class:
                names = self._get_local_symbols(current)
                own_name = self._get_defined_name(current)
                if own_name:
                    names.discard(own_name)
                    body = current.child_by_field_name("body")
                    if body:
                        names.update(self._get_local_symbols(body))
                    parameters = current.child_by_field_name("parameters")
                    if parameters:
                        names.update(self._get_local_symbols(parameters))
            else:
                names = self._get_local_symbols(current)
            visible.update(names)
            current = parent
        visible.update(self._get_local_symbols(ast))
        return visible

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
        if node.type in {"function_definition", "class_definition"}:
            name = node.child_by_field_name("name")
        elif node.type == "assignment":
            name = node.child_by_field_name("left")
        elif node.type in {
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        }:
            name = next(
                (child for child in node.children if child.type == "identifier"), None
            )
        else:
            return None
        if name and name.type == "identifier" and name.text:
            return name.text.decode("utf-8")
        return None

    def _get_local_symbols(self, scope_node: Node) -> set[str]:
        """Include imports defined directly in this scope."""
        names = super()._get_local_symbols(scope_node)

        def collect_targets(node: Node) -> None:
            if node.type == "identifier" and node.text:
                names.add(node.text.decode("utf-8"))
            elif node.type in {
                "pattern_list",
                "list_pattern",
                "tuple_pattern",
                "list_splat_pattern",
                "dictionary_splat_pattern",
                "parameters",
                "as_pattern_target",
            }:
                for child in node.named_children:
                    collect_targets(child)
            elif node.type in {
                "typed_parameter",
                "default_parameter",
                "typed_default_parameter",
            }:
                target = node.child_by_field_name("name") or next(
                    (
                        child
                        for child in node.named_children
                        if child.type == "identifier"
                    ),
                    None,
                )
                if target:
                    collect_targets(target)

        def collect_imports(node: Node, depth: int = 0) -> None:
            if depth > 0 and self._is_scope_node(node):
                return
            if self._is_import_node(node):
                names.update(self._extract_imported_names(node))
            if node.type in {"assignment", "for_statement", "for_in_clause"}:
                target = node.child_by_field_name("left")
                if target:
                    collect_targets(target)
            elif node.type == "parameters":
                collect_targets(node)
            elif node.type == "as_pattern":
                alias = node.child_by_field_name("alias")
                if alias:
                    collect_targets(alias)
            elif node.type == "named_expression":
                target = node.child_by_field_name("name")
                if target:
                    collect_targets(target)
            for child in node.children:
                collect_imports(child, depth + 1)

        collect_imports(scope_node)
        return names

    def _get_imported_symbols(self, ast: Node) -> set[str]:
        """Imports are included through their declaring scopes."""
        return set()

    @staticmethod
    def _extract_imported_names(import_node: Node) -> set[str]:
        """Extract symbol names from an import node."""
        names = set()
        if import_node.type == "import_statement":
            for child in import_node.children:
                if child.type == "dotted_name":
                    first = child.named_children[0] if child.named_children else None
                    if first and first.text:
                        names.add(first.text.decode("utf-8"))
                elif child.type == "aliased_import":
                    alias = child.child_by_field_name("alias")
                    if alias and alias.text:
                        names.add(alias.text.decode("utf-8"))
        elif import_node.type == "import_from_statement":
            in_import_list = False
            for child in import_node.children:
                if child.type == "import":
                    in_import_list = True
                elif in_import_list and child.type == "dotted_name" and child.text:
                    names.add(child.text.decode("utf-8"))
                elif in_import_list and child.type == "aliased_import":
                    alias = child.child_by_field_name("alias")
                    if alias and alias.text:
                        names.add(alias.text.decode("utf-8"))
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
