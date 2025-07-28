"""JavaScript/TypeScript-specific metadata extraction."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo
from chunker.metadata.extractor import BaseMetadataExtractor
from chunker.metadata.metrics import BaseComplexityAnalyzer


class JavaScriptMetadataExtractor(BaseMetadataExtractor):
    """JavaScript/TypeScript-specific metadata extraction implementation."""

    def __init__(self, language: str = "javascript"):
        """Initialize the JavaScript metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function/method signature information."""
        if node.type not in (
            "function_declaration",
            "method_definition",
            "arrow_function",
            "function",
            "function_expression",
            "generator_function_declaration",
        ):
            return None

        # Get function name
        name = None
        if node.type in (
            "function_declaration",
            "method_definition",
            "generator_function_declaration",
        ):
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                name = self._get_node_text(name_node, source)
        elif node.type == "function_expression":
            # Named function expression
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                name = self._get_node_text(name_node, source)
        # Arrow functions typically don't have names unless assigned

        # For methods, get the property name
        if node.type == "method_definition":
            prop_name_node = self._find_child_by_type(node, "property_identifier")
            if prop_name_node:
                name = self._get_node_text(prop_name_node, source)

        # Get parameters
        parameters = []
        params_node = self._find_child_by_type(node, "formal_parameters")
        if params_node:
            parameters = self._extract_parameters(params_node, source)

        # Get return type (TypeScript)
        return_type = None
        type_annotation_node = self._find_child_by_type(node, "type_annotation")
        if type_annotation_node:
            return_type = (
                self._get_node_text(type_annotation_node, source).strip(":").strip()
            )

        # Get decorators (TypeScript)
        decorators = []
        if node.parent and node.parent.type == "decorator":
            decorator_text = self._get_node_text(node.parent, source).strip("@")
            decorators.append(decorator_text)

        # Get modifiers (async, static, private, etc.)
        modifiers = []

        # Check for async
        if self._has_async_modifier(node, source):
            modifiers.append("async")

        # Check for generator
        if node.type == "generator_function_declaration" or self._is_generator(
            node,
            source,
        ):
            modifiers.append("generator")

        # Check for static/private/public modifiers
        # For method_definition, modifiers are direct children
        if node.type == "method_definition":
            for child in node.children:
                if child.type in (
                    "static",
                    "private",
                    "public",
                    "protected",
                    "readonly",
                ):
                    modifiers.append(child.type)
                elif child.type == "async" and "async" not in modifiers:
                    modifiers.append("async")

        return SignatureInfo(
            name=name or "<anonymous>",
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
        )

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract JSDoc comment from a node."""
        # Look for JSDoc comment before the node
        if node.parent:
            siblings = node.parent.children
            node_index = siblings.index(node) if node in siblings else -1

            if node_index > 0:
                prev_node = siblings[node_index - 1]
                if prev_node.type == "comment" and self._is_jsdoc_comment(
                    prev_node,
                    source,
                ):
                    return self._parse_jsdoc(prev_node, source)

        # Also check leading comment
        comment = self._extract_leading_comment(node, source)
        if comment and comment.strip().startswith("/**"):
            return self._clean_jsdoc_comment(comment)

        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract import statements used within a node."""
        imports = []

        def collect_imports(n: Node, depth: int):
            if n.type in ("import_statement", "import_clause"):
                imports.append(self._get_node_text(n, source).strip())
            # Also collect require() calls
            elif n.type == "call_expression":
                func_node = self._find_child_by_type(n, "identifier")
                if func_node and self._get_node_text(func_node, source) == "require":
                    imports.append(self._get_node_text(n, source).strip())

        self._walk_tree(node, collect_imports)
        return imports

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk depends on."""
        dependencies = set()

        # Get all identifiers
        identifiers = self._extract_identifiers(node, source)

        # Get defined symbols within this node
        defined = self._extract_defined_symbols(node, source)

        # Dependencies are referenced but not defined
        dependencies = identifiers - defined

        # Remove JavaScript globals and common APIs
        js_builtins = {
            "console",
            "window",
            "document",
            "global",
            "process",
            "module",
            "exports",
            "require",
            "import",
            "export",
            "default",
            "undefined",
            "null",
            "this",
            "super",
            "new",
            "typeof",
            "instanceof",
            "delete",
            "void",
            "in",
            "of",
            "true",
            "false",
            "NaN",
            "Infinity",
            "Object",
            "Array",
            "String",
            "Number",
            "Boolean",
            "Function",
            "Symbol",
            "Date",
            "RegExp",
            "Error",
            "JSON",
            "Math",
            "Promise",
            "Set",
            "Map",
            "WeakSet",
            "WeakMap",
            "Proxy",
            "Reflect",
            "parseInt",
            "parseFloat",
            "isNaN",
            "isFinite",
            "alert",
            "prompt",
            "confirm",
            "setTimeout",
            "setInterval",
            "clearTimeout",
            "clearInterval",
            "addEventListener",
            "removeEventListener",
            "fetch",
            "XMLHttpRequest",
        }
        dependencies -= js_builtins

        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk exports/defines."""
        exports = set()

        # Function/method name
        if node.type in ("function_declaration", "method_definition"):
            name_node = self._find_child_by_type(node, "identifier")
            if not name_node and node.type == "method_definition":
                name_node = self._find_child_by_type(node, "property_identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))

        # Class name
        elif node.type == "class_declaration":
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))

        # Variable declarations
        elif node.type in ("variable_declaration", "lexical_declaration"):
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = self._find_child_by_type(child, "identifier")
                    if name_node:
                        exports.add(self._get_node_text(name_node, source))

        # Export statements
        self._extract_export_symbols(node, source, exports)

        return exports

    # Helper methods

    def _extract_parameters(
        self,
        params_node: Node,
        source: bytes,
    ) -> list[dict[str, Any]]:
        """Extract parameter information from formal_parameters node."""
        parameters = []

        for child in params_node.children:
            if child.type in (
                "identifier",
                "required_parameter",
                "optional_parameter",
                "rest_parameter",
                "object_pattern",
                "array_pattern",
                "assignment_pattern",
            ):  # Added assignment_pattern for default params
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
        param_info = {
            "name": None,
            "type": None,
            "default": None,
        }

        if param_node.type == "identifier":
            param_info["name"] = self._get_node_text(param_node, source)

        elif param_node.type == "required_parameter":
            # TypeScript: name: type
            pattern_node = self._find_child_by_type(param_node, "identifier")
            if pattern_node:
                param_info["name"] = self._get_node_text(pattern_node, source)
            type_node = self._find_child_by_type(param_node, "type_annotation")
            if type_node:
                param_info["type"] = (
                    self._get_node_text(type_node, source).strip(":").strip()
                )

        elif param_node.type == "optional_parameter":
            # name?: type or name = default
            pattern_node = self._find_child_by_type(param_node, "identifier")
            if pattern_node:
                param_info["name"] = self._get_node_text(pattern_node, source)
                # Check if it's optional (has ?)
                text = self._get_node_text(param_node, source)
                if "?" in text:
                    param_info["name"] += "?"
            # Check for default value
            for child in param_node.children:
                if child.type == "=":
                    # Next sibling is default value
                    idx = param_node.children.index(child)
                    if idx + 1 < len(param_node.children):
                        param_info["default"] = self._get_node_text(
                            param_node.children[idx + 1],
                            source,
                        )

        elif param_node.type == "rest_parameter":
            # ...args
            identifier = self._find_child_by_type(param_node, "identifier")
            if identifier:
                param_info["name"] = "..." + self._get_node_text(identifier, source)

        elif param_node.type in ("object_pattern", "array_pattern"):
            # Destructuring parameter
            param_info["name"] = self._get_node_text(param_node, source)

        elif param_node.type == "assignment_pattern":
            # Parameter with default value (e.g., b = 0)
            # First child is the parameter name, last child is the default value
            if len(param_node.children) >= 3:
                param_info["name"] = self._get_node_text(param_node.children[0], source)
                param_info["default"] = self._get_node_text(
                    param_node.children[2],
                    source,
                )

        return param_info if param_info["name"] else None

    def _has_async_modifier(self, node: Node, source: bytes) -> bool:
        """Check if function has async modifier."""
        # Check if 'async' keyword appears before the function
        if node.parent:
            siblings = node.parent.children
            node_index = siblings.index(node) if node in siblings else -1
            if node_index > 0:
                prev_sibling = siblings[node_index - 1]
                if prev_sibling.type == "async":
                    return True

        # For arrow functions, check the text
        text = self._get_node_text(node, source)
        return text.strip().startswith("async ")

    def _is_generator(self, node: Node, source: bytes) -> bool:
        """Check if function is a generator."""
        return (
            node.type == "generator_function_declaration"
            or "*" in self._get_node_text(node, source)[:20]
        )

    def _is_jsdoc_comment(self, node: Node, source: bytes) -> bool:
        """Check if comment is JSDoc format."""
        text = self._get_node_text(node, source)
        return text.strip().startswith("/**") and text.strip().endswith("*/")

    def _parse_jsdoc(self, comment_node: Node, source: bytes) -> str:
        """Parse JSDoc comment."""
        text = self._get_node_text(comment_node, source)
        return self._clean_jsdoc_comment(text)

    def _clean_jsdoc_comment(self, comment: str) -> str:
        """Clean JSDoc comment text."""
        lines = comment.strip().split("\n")
        cleaned = []

        for line in lines:
            line = line.strip()
            # Remove /** and */
            if line in ("/**", "*/"):
                continue
            # Remove leading *
            if line.startswith("*"):
                line = line[1:].strip()
            cleaned.append(line)

        return "\n".join(cleaned).strip()

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()

        def collect_definitions(n: Node, depth: int):
            # Function declarations
            if n.type in {"function_declaration", "class_declaration"}:
                name_node = self._find_child_by_type(n, "identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))

            # Variable declarations
            elif n.type in ("variable_declarator", "const_declaration"):
                id_node = self._find_child_by_type(n, "identifier")
                if id_node:
                    defined.add(self._get_node_text(id_node, source))

            # Parameter names
            elif n.type == "formal_parameters":
                for param in n.children:
                    if param.type == "identifier":
                        defined.add(self._get_node_text(param, source))

        self._walk_tree(node, collect_definitions)
        return defined

    def _extract_export_symbols(self, node: Node, source: bytes, exports: set[str]):
        """Extract exported symbols."""

        def collect_exports(n: Node, depth: int):
            if n.type == "export_statement":
                # Check what's being exported
                for child in n.children:
                    if child.type in ("function_declaration", "class_declaration"):
                        name_node = self._find_child_by_type(child, "identifier")
                        if name_node:
                            exports.add(self._get_node_text(name_node, source))
                    elif child.type == "lexical_declaration":
                        # const/let exports
                        for declarator in child.children:
                            if declarator.type == "variable_declarator":
                                id_node = self._find_child_by_type(
                                    declarator,
                                    "identifier",
                                )
                                if id_node:
                                    exports.add(self._get_node_text(id_node, source))

        self._walk_tree(node, collect_exports)


class JavaScriptComplexityAnalyzer(BaseComplexityAnalyzer):
    """JavaScript/TypeScript-specific complexity analysis."""

    def __init__(self):
        super().__init__("javascript")

    def _get_decision_point_types(self) -> set[str]:
        """Get JavaScript-specific decision point types."""
        base = super()._get_decision_point_types()
        js_specific = {
            "if_statement",
            "else_clause",
            "while_statement",
            "for_statement",
            "for_in_statement",
            "for_of_statement",
            "do_statement",
            "switch_statement",
            "case_clause",
            "try_statement",
            "catch_clause",
            "finally_clause",
            "conditional_expression",  # ternary
            "binary_expression",  # for && and ||
            "logical_expression",
        }
        return base.union(js_specific)

    def _get_cognitive_complexity_factors(self) -> dict[str, int]:
        """Get JavaScript-specific cognitive complexity factors."""
        base = super()._get_cognitive_complexity_factors()
        js_specific = {
            "if_statement": 1,
            "else_clause": 0,
            "while_statement": 1,
            "for_statement": 1,
            "for_in_statement": 1,
            "for_of_statement": 1,
            "do_statement": 1,
            "switch_statement": 1,
            "case_clause": 0,
            "try_statement": 1,
            "catch_clause": 1,
            "finally_clause": 0,
            "conditional_expression": 1,
            "binary_expression": 0,  # Will be checked for && ||
            "logical_expression": 1,
            "arrow_function": 0,  # Inline functions don't add complexity
            "recursive_call": 1,
        }
        return {**base, **js_specific}

    def _increases_nesting(self, node_type: str) -> bool:
        """Check if JavaScript node type increases nesting."""
        return node_type in {
            "if_statement",
            "while_statement",
            "for_statement",
            "for_in_statement",
            "for_of_statement",
            "do_statement",
            "switch_statement",
            "try_statement",
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "class_declaration",
            "block_statement",
        }

    def _is_comment_line(self, line: str) -> bool:
        """Check if line is a JavaScript comment."""
        line = line.strip()
        return line.startswith(("//", "/*", "*")) or line.endswith("*/") or line == "*/"
