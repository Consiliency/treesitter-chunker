"""Python-specific metadata extraction."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo
from chunker.metadata.extractor import BaseMetadataExtractor
from chunker.metadata.metrics import BaseComplexityAnalyzer


class PythonMetadataExtractor(BaseMetadataExtractor):
    """Python-specific metadata extraction implementation."""

    def __init__(self, language: str = "python"):
        """Initialize the Python metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function/method signature information."""
        if node.type not in {"function_definition", "method_definition"}:
            return None
        name_node = self._find_child_by_type(node, "identifier")
        if not name_node:
            return None
        name = self._get_node_text(name_node, source)
        parameters = []
        params_node = self._find_child_by_type(node, "parameters")
        if params_node:
            parameters = self._extract_parameters(params_node, source)
        return_type = None
        return_type_node = self._find_child_by_type(node, "type")
        if return_type_node:
            return_type = self._get_node_text(return_type_node, source)
        decorators = []
        if node.parent and node.parent.type == "decorated_definition":
            decorator_nodes = self._find_all_children_by_type(node.parent, "decorator")
            decorators = [
                self._get_node_text(d, source).strip("@") for d in decorator_nodes
            ]
        modifiers = []
        if self._has_async_modifier(node, source):
            modifiers.append("async")
        modifiers.extend(
            decorator
            for decorator in decorators
            if decorator in {"staticmethod", "classmethod"}
        )
        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract docstring from a node."""
        body_node = self._find_child_by_type(node, "block")
        if not body_node:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                string_node = self._find_string_node(child)
                if string_node:
                    docstring = self._get_node_text(string_node, source)
                    if docstring.startswith(('"""', "'''")):
                        docstring = docstring[3:-3]
                    elif docstring.startswith(('"', "'")):
                        docstring = docstring[1:-1]
                    return docstring.strip()
        comment = self._extract_leading_comment(node, source)
        if comment:
            return comment.strip("#").strip()
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract import statements used within a node."""
        imports = []

        def collect_imports(n: Node, _depth: int):
            if n.type in {"import_statement", "import_from_statement"}:
                imports.append(self._get_node_text(n, source).strip())

        self._walk_tree(node, collect_imports)
        return imports

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk depends on."""
        dependencies = set()
        identifiers = self._extract_identifiers(node, source)
        defined = self._extract_defined_symbols(node, source)
        dependencies = identifiers - defined
        builtins = {
            "print",
            "len",
            "range",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "type",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "delattr",
            "None",
            "True",
            "False",
            "self",
            "cls",
            "super",
            "object",
            "Exception",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "AttributeError",
            "open",
            "file",
            "input",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "enumerate",
            "all",
            "any",
            "sum",
            "min",
            "max",
            "abs",
            "round",
            "pow",
            "divmod",
        }
        dependencies -= builtins
        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk exports/defines."""
        exports = set()
        if (
            node.type
            in {
                "function_definition",
                "method_definition",
            }
            or node.type == "class_definition"
        ):
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))
        nested = self._extract_defined_symbols(node, source)
        exports.update(nested)
        return exports

    def _extract_parameters(
        self,
        params_node: Node,
        source: bytes,
    ) -> list[dict[str, Any]]:
        """Extract parameter information from parameters node."""
        parameters = []
        for child in params_node.children:
            if child.type in {
                "identifier",
                "typed_parameter",
                "default_parameter",
                "typed_default_parameter",
                "list_splat_pattern",
                "dictionary_splat_pattern",
            }:
                param = self._parse_parameter(child, source)
                if param:
                    parameters.append(param)
        return parameters

    def _parse_parameter(
        self,
        param_node: Node,
        source: bytes,
    ) -> dict[str, Any] | None:
        """Parse a single parameter node."""
        param_info = {"name": None, "type": None, "default": None}
        if param_node.type == "identifier":
            param_info["name"] = self._get_node_text(param_node, source)
        elif param_node.type == "typed_parameter":
            name_node = self._find_child_by_type(param_node, "identifier")
            type_node = self._find_child_by_type(param_node, "type")
            if name_node:
                param_info["name"] = self._get_node_text(name_node, source)
            if type_node:
                param_info["type"] = self._get_node_text(type_node, source)
        elif param_node.type == "default_parameter":
            name_node = self._find_child_by_type(param_node, "identifier")
            if name_node:
                param_info["name"] = self._get_node_text(name_node, source)
            for i, child in enumerate(param_node.children):
                if child.type == "=" and i + 1 < len(param_node.children):
                    param_info["default"] = self._get_node_text(
                        param_node.children[i + 1],
                        source,
                    )
        elif param_node.type == "typed_default_parameter":
            name_node = self._find_child_by_type(param_node, "identifier")
            type_node = self._find_child_by_type(param_node, "type")
            if name_node:
                param_info["name"] = self._get_node_text(name_node, source)
            if type_node:
                param_info["type"] = self._get_node_text(type_node, source)
            for i, child in enumerate(param_node.children):
                if child.type == "=" and i + 1 < len(param_node.children):
                    param_info["default"] = self._get_node_text(
                        param_node.children[i + 1],
                        source,
                    )
        elif param_node.type == "list_splat_pattern":
            param_info["name"] = "*" + self._get_node_text(
                param_node,
                source,
            ).strip("*")
        elif param_node.type == "dictionary_splat_pattern":
            param_info["name"] = "**" + self._get_node_text(
                param_node,
                source,
            ).strip("*")
        return param_info if param_info["name"] else None

    def _has_async_modifier(self, node: Node, source: bytes) -> bool:
        """Check if function has async modifier."""
        text = self._get_node_text(node, source)
        return text.strip().startswith("async ")

    def _find_string_node(self, node: Node) -> Node | None:
        """Find string node in expression."""
        for child in node.children:
            if child.type in {"string", "concatenated_string"}:
                return child
            result = self._find_string_node(child)
            if result:
                return result
        return None

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()

        def collect_definitions(n: Node, _depth: int):
            if n.type in {
                "function_definition",
                "method_definition",
                "class_definition",
            }:
                self._add_named_definition(n, source, defined)
            elif n.type == "assignment":
                self._add_assignment_definition(n, source, defined)
            elif n.type == "parameters":
                self._add_parameter_definitions(n, source, defined)
            elif n.type == "for_statement":
                self._add_for_loop_variable(n, source, defined)
            elif n.type in {
                "list_comprehension",
                "dictionary_comprehension",
                "set_comprehension",
                "generator_expression",
            }:
                self._add_comprehension_variables(n, source, defined)

        self._walk_tree(node, collect_definitions)
        return defined

    def _add_named_definition(self, node: Node, source: bytes, defined: set[str]):
        """Add function, method, or class definition."""
        name_node = self._find_child_by_type(node, "identifier")
        if name_node:
            defined.add(self._get_node_text(name_node, source))

    def _add_assignment_definition(self, node: Node, source: bytes, defined: set[str]):
        """Add assignment target definition."""
        left_node = self._find_child_by_type(node, "identifier")
        if left_node:
            defined.add(self._get_node_text(left_node, source))

    def _add_parameter_definitions(self, node: Node, source: bytes, defined: set[str]):
        """Add parameter definitions from function signature."""
        for param in node.children:
            if param.type == "identifier":
                defined.add(self._get_node_text(param, source))
            elif param.type in {
                "typed_parameter",
                "default_parameter",
                "typed_default_parameter",
            }:
                id_node = self._find_child_by_type(param, "identifier")
                if id_node:
                    defined.add(self._get_node_text(id_node, source))

    def _add_for_loop_variable(self, node: Node, source: bytes, defined: set[str]):
        """Add for loop iteration variable."""
        pattern = PythonMetadataExtractor._find_for_loop_pattern(node)
        if pattern and pattern.type == "identifier":
            defined.add(self._get_node_text(pattern, source))

    @staticmethod
    def _find_for_loop_pattern(node: Node) -> Node | None:
        """Find the iteration variable pattern in a for loop."""
        for i, child in enumerate(node.children):
            if child.type == "in" and i > 0:
                return node.children[i - 1]
        return None

    def _add_comprehension_variables(
        self,
        node: Node,
        source: bytes,
        defined: set[str],
    ):
        """Add variables from comprehension expressions."""
        for child in node.children:
            if child.type == "for_in_clause":
                var_node = PythonMetadataExtractor._find_comprehension_variable(child)
                if var_node and var_node.type == "identifier":
                    defined.add(self._get_node_text(var_node, source))

    @staticmethod
    def _find_comprehension_variable(for_in_clause: Node) -> Node | None:
        """Find the iteration variable in a for_in_clause."""
        for i, child in enumerate(for_in_clause.children):
            if child.type == "for" and i + 1 < len(for_in_clause.children):
                return for_in_clause.children[i + 1]
        return None


class PythonComplexityAnalyzer(BaseComplexityAnalyzer):
    """Python-specific complexity analysis."""

    def __init__(self):
        super().__init__("python")

    def _get_decision_point_types(self) -> set[str]:
        """Get Python-specific decision point types."""
        base = super()._get_decision_point_types()
        python_specific = {
            "if_statement",
            "elif_clause",
            "while_statement",
            "for_statement",
            "try_statement",
            "except_clause",
            "with_statement",
            "match_statement",
            "case_clause",
            "conditional_expression",
            "boolean_operator",
            "list_comprehension",
            "dictionary_comprehension",
            "set_comprehension",
            "generator_expression",
        }
        return base.union(python_specific)

    def _get_cognitive_complexity_factors(self) -> dict[str, int]:
        """Get Python-specific cognitive complexity factors."""
        base = super()._get_cognitive_complexity_factors()
        python_specific = {
            "if_statement": 1,
            "elif_clause": 1,
            "else_clause": 0,
            "while_statement": 1,
            "for_statement": 1,
            "try_statement": 1,
            "except_clause": 1,
            "finally_clause": 0,
            "with_statement": 1,
            "match_statement": 1,
            "case_clause": 0,
            "conditional_expression": 1,
            "boolean_operator": 1,
            "list_comprehension": 1,
            "dictionary_comprehension": 1,
            "set_comprehension": 1,
            "generator_expression": 1,
            "lambda": 0,
            "recursive_call": 1,
        }
        return {**base, **python_specific}

    @staticmethod
    def _increases_nesting(node_type: str) -> bool:
        """Check if Python node type increases nesting."""
        return node_type in {
            "if_statement",
            "while_statement",
            "for_statement",
            "try_statement",
            "with_statement",
            "match_statement",
            "function_definition",
            "class_definition",
            "list_comprehension",
            "dictionary_comprehension",
            "set_comprehension",
            "generator_expression",
        }

    @staticmethod
    def _is_comment_line(line: str) -> bool:
        """Check if line is a Python comment."""
        line = line.strip()
        return (
            line.startswith(("#", '"""', "'''"))
            or line
            in {
                '"""',
                "'''",
            }
            or not line
        )
