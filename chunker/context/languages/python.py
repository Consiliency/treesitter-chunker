"""Python-specific context extraction implementation."""

from collections.abc import Iterator

from tree_sitter import Node

from chunker.context.extractor import BaseContextExtractor
from chunker.context.filter import BaseContextFilter
from chunker.context.scope_analyzer import BaseScopeAnalyzer
from chunker.context.symbol_resolver import BaseSymbolResolver
from chunker.interfaces.context import ContextItem, ContextType

_COMPREHENSION_SCOPES = frozenset(
    {
        "list_comprehension",
        "set_comprehension",
        "dictionary_comprehension",
        "generator_expression",
    }
)
_FUNCTION_SCOPES = frozenset({"function_definition", "lambda"})
_DEFAULT_PARAMETERS = frozenset({"default_parameter", "typed_default_parameter"})
_PARAMETER_LISTS = frozenset({"parameters", "lambda_parameters"})
_SPLAT_PATTERNS = frozenset({"list_splat_pattern", "dictionary_splat_pattern"})


def _is_parameter_name(node: Node) -> bool:
    """Check plain and splat parameter names on their declaration side."""
    parent = node.parent
    if node.type != "identifier" or parent is None:
        return False
    if parent.type in _PARAMETER_LISTS:
        return True
    if parent.type not in _SPLAT_PATTERNS:
        return False
    parameters = parent.parent
    if parameters is not None and parameters.type == "typed_parameter":
        parameters = parameters.parent
    return parameters is not None and parameters.type in _PARAMETER_LISTS


def _target_container(identifier: Node) -> Node | None:
    """Climb destructuring wrappers, stopping at selectors and subscripts."""
    target = identifier
    while target.parent is not None and target.parent.type in {
        "pattern_list",
        "tuple_pattern",
        "list_pattern",
        "tuple",
        "list",
        "list_splat_pattern",
        "list_splat",
        "parenthesized_expression",
    }:
        target = target.parent
    container = target.parent
    if container is None:
        return None
    if container.type == "as_pattern_target":
        return container
    if (
        container.type in {"assignment", "for_statement", "for_in_clause"}
        and container.child_by_field_name("left") == target
    ):
        return container
    return None


def _header_expressions(node: Node) -> Iterator[Node]:
    """Expressions in a nested declaration evaluated by its enclosing scope."""
    bases = node.child_by_field_name("superclasses")
    if bases is not None:
        yield bases
    parameters = node.child_by_field_name("parameters")
    if parameters is not None:
        for param in parameters.named_children:
            value = param.child_by_field_name("value")
            if param.type in _DEFAULT_PARAMETERS and value is not None:
                yield value


def _escaping_walruses(node: Node) -> Iterator[Node]:
    if node.type == "named_expression":
        yield node
    children = (
        _header_expressions(node)
        if node.type in _FUNCTION_SCOPES or node.type == "class_definition"
        else node.named_children
    )
    for child in children:
        yield from _escaping_walruses(child)


def _scope_candidates(scope: Node) -> Iterator[Node]:
    """Traverse this owner's bindings in syntax order, pruning nested bodies."""

    def visit(node: Node) -> Iterator[Node]:
        if node != scope:
            if (
                node.type != "named_expression"
                or scope.type not in _COMPREHENSION_SCOPES
            ):
                yield node
            if node.type in _FUNCTION_SCOPES or node.type == "class_definition":
                if scope.type not in _COMPREHENSION_SCOPES:
                    for expr in _header_expressions(node):
                        yield from _escaping_walruses(expr)
                return
            if node.type in _COMPREHENSION_SCOPES:
                if scope.type not in _COMPREHENSION_SCOPES:
                    yield from _escaping_walruses(node)
                return
        default = (
            node.child_by_field_name("value")
            if node.type in _DEFAULT_PARAMETERS
            else None
        )
        bases = (
            node.child_by_field_name("superclasses")
            if node.type == "class_definition"
            else None
        )
        for child in node.named_children:
            if child != default and child != bases:
                yield from visit(child)

    yield from visit(scope)


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
        if parent.type == "attribute":
            return parent.child_by_field_name("attribute") == identifier_node
        if parent.type == "keyword_argument":
            return parent.child_by_field_name("name") == identifier_node
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
        if parent.type in {"default_parameter", "typed_default_parameter"}:
            return parent.child_by_field_name("name") == identifier_node
        if parent.type in {
            "parameters",
            "lambda_parameters",
            "typed_parameter",
            "identifier",
        }:
            return True
        if (
            parent.type == "named_expression"
            and parent.child_by_field_name("name") == identifier_node
        ):
            return True
        if (
            _is_parameter_name(identifier_node)
            or _target_container(identifier_node) is not None
        ):
            return True
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
        if _is_parameter_name(node):
            return True
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
        if node.type == "identifier":
            if not _is_parameter_name(node):
                return None
            return node.text.decode("utf-8") if node.text else None
        return PythonScopeAnalyzer._get_defined_name(node)

    def _binding_for(self, node: Node, name: str) -> Node | None:
        if node.type in {
            "import_statement",
            "import_from_statement",
            "future_import_statement",
        }:
            return (
                node
                if name in PythonScopeAnalyzer._extract_imported_names(node)
                else None
            )
        if node.type == "named_expression":
            target = node.child_by_field_name("name")
            return target if target and self._get_node_text(target) == name else None
        if self._is_definition_node(node) and self._get_defined_name(node) == name:
            return node
        if node.type != "identifier" or self._get_node_text(node) != name:
            return None
        container = _target_container(node)
        if container is None:
            return None
        if container.type == "assignment":
            return container
        if container.type == "as_pattern_target":
            pattern = container.parent
            if (
                pattern is None
                or pattern.parent is None
                or pattern.parent.type not in {"with_item", "except_clause"}
            ):
                return None
        return node

    def _lookup_definition(
        self, symbol_name: str, scope_node: Node, ast: Node
    ) -> Node | None:
        current: Node | None = scope_node
        while current is not None:
            first = None
            directive = None
            for candidate in _scope_candidates(current):
                if (
                    candidate.type in {"global_statement", "nonlocal_statement"}
                    and current != ast
                ):
                    if any(
                        self._get_node_text(n) == symbol_name
                        for n in candidate.named_children
                    ):
                        directive = candidate.type
                        break
                elif first is None:
                    first = self._binding_for(candidate, symbol_name)
                    # Directives cannot redirect a parameter, a module binding,
                    # or a comprehension iteration target.
                    if first is not None and (
                        current == ast
                        or current.type in _COMPREHENSION_SCOPES
                        or first.type in _DEFAULT_PARAMETERS
                        or first.type == "typed_parameter"
                        or _is_parameter_name(first)
                    ):
                        return first
            if directive is None and first is not None:
                return first
            if current == ast:
                return None
            current = (
                ast
                if directive == "global_statement"
                else self._get_parent_scope(current) or ast
            )
        return None

    def _get_parent_scope(self, node: Node) -> Node | None:
        """Cross nested defaults and outermost iterables in their evaluation scope."""
        child = node
        parent = node.parent
        skip = None
        while parent is not None:
            if (
                parent.type in _DEFAULT_PARAMETERS
                and parent.child_by_field_name("value") == child
                and parent.parent is not None
            ):
                skip = parent.parent.parent
            elif (
                parent.type == "for_in_clause"
                and parent.child_by_field_name("right") == child
            ):
                comp = parent.parent
                if comp is not None and comp.type in _COMPREHENSION_SCOPES:
                    first = next(
                        (c for c in comp.named_children if c.type == "for_in_clause"),
                        None,
                    )
                    if parent == first:
                        skip = comp
            elif (
                self._creates_new_scope(parent)
                and parent != skip
                and parent.type != "class_definition"
            ):
                return parent
            child, parent = parent, parent.parent
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

    # The interface declares this method static; BaseScopeAnalyzer already
    # overrides it as an instance method and carries the same baseline mypy
    # signature (chunker/context/scope_analyzer.py).
    def get_enclosing_scope(self, node: Node) -> Node | None:  # type: ignore[override]
        """Return the scope in which ``node`` is evaluated.

        Parameter default values are evaluated in the scope that contains the
        function or lambda, so the owning function is skipped for nodes inside
        a default value.
        """
        if node in self._scope_cache:
            return self._scope_cache[node]
        skipped = None
        child = node
        current = node.parent
        while current:
            if (
                current.type in _DEFAULT_PARAMETERS
                and current.child_by_field_name("value") == child
                and current.parent is not None
            ):
                skipped = current.parent.parent
            if self._is_scope_node(current) and current != skipped:
                break
            child = current
            current = current.parent
        if len(self._scope_cache) >= 256:
            self._scope_cache.pop(next(iter(self._scope_cache)))
        self._scope_cache[node] = current
        return current

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
                "lambda_parameters",
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
                        if child.type
                        in {
                            "identifier",
                            "list_splat_pattern",
                            "dictionary_splat_pattern",
                        }
                    ),
                    None,
                )
                if target:
                    collect_targets(target)
            elif node.type in {"type", "generic_type"} and node.named_children:
                collect_targets(node.named_children[0])

        def collect_case_bindings(node: Node) -> None:
            if node.type == "identifier" and node.text:
                names.add(node.text.decode("utf-8"))
            elif node.type == "dotted_name":
                if (
                    len(node.named_children) == 1
                    and node.text == node.named_children[0].text
                ):
                    collect_case_bindings(node.named_children[0])
            elif node.type == "class_pattern":
                for child in node.named_children:
                    if child.type == "case_pattern":
                        collect_case_bindings(child)
            elif node.type == "dict_pattern":
                for child in node.named_children:
                    if child.type in {"case_pattern", "splat_pattern"}:
                        collect_case_bindings(child)
            elif node.type == "keyword_pattern":
                value = node.children[-1]
                if value.is_named:
                    collect_case_bindings(value)
            elif node.type in {
                "case_pattern",
                "list_pattern",
                "tuple_pattern",
                "union_pattern",
                "splat_pattern",
                "as_pattern",
            }:
                for child in node.named_children:
                    collect_case_bindings(child)

        def collect_parameter_defaults(function: Node) -> None:
            parameters = function.child_by_field_name("parameters")
            for parameter in parameters.named_children if parameters else ():
                value = parameter.child_by_field_name("value")
                if parameter.type in _DEFAULT_PARAMETERS and value:
                    collect_assignment_expressions(value)

        def collect_assignment_expressions(node: Node) -> None:
            """Collect walrus targets that bind in the scope being collected.

            Comprehensions do not own assignment-expression targets, and
            parameter defaults are evaluated in the enclosing scope.
            """
            if node.type == "named_expression":
                target = node.child_by_field_name("name")
                if target and target.text:
                    names.add(target.text.decode("utf-8"))
            if node.type in _FUNCTION_SCOPES:
                collect_parameter_defaults(node)
                return
            if node.type == "class_definition":
                return
            for child in node.children:
                collect_assignment_expressions(child)

        owns_assignment_expressions = scope_node.type not in _COMPREHENSION_SCOPES

        def collect_imports(node: Node, depth: int = 0) -> None:
            if depth > 0 and self._is_scope_node(node):
                if owns_assignment_expressions:
                    if node.type in _COMPREHENSION_SCOPES:
                        collect_assignment_expressions(node)
                    elif node.type in _FUNCTION_SCOPES:
                        collect_parameter_defaults(node)
                return
            if node.type == "named_expression" and owns_assignment_expressions:
                target = node.child_by_field_name("name")
                if target and target.text:
                    names.add(target.text.decode("utf-8"))
            if self._is_import_node(node):
                names.update(self._extract_imported_names(node))
            if node.type in {
                "assignment",
                "for_statement",
                "for_in_clause",
                "type_alias_statement",
            }:
                target = node.child_by_field_name("left")
                if target:
                    collect_targets(target)
            elif node.type in {"parameters", "lambda_parameters"}:
                collect_targets(node)
                return
            elif node.type == "as_pattern":
                alias = node.child_by_field_name("alias")
                if alias:
                    collect_targets(alias)
            elif node.type == "case_clause":
                for pattern in node.named_children:
                    if pattern.type == "case_pattern":
                        collect_case_bindings(pattern)
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
        elif import_node.type in {"import_from_statement", "future_import_statement"}:
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
