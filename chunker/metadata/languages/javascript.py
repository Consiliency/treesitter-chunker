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
        if node.type not in {
            "function_declaration",
            "method_definition",
            "arrow_function",
            "function",
            "function_expression",
            "generator_function_declaration",
        }:
            return None
        name = None
        if (
            node.type
            in {
                "function_declaration",
                "method_definition",
                "generator_function_declaration",
            }
            or node.type == "function_expression"
        ):
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                name = self._get_node_text(name_node, source)
        if node.type == "method_definition":
            prop_name_node = self._find_child_by_type(node, "property_identifier")
            if prop_name_node:
                name = self._get_node_text(prop_name_node, source)
        parameters = []
        params_node = self._find_child_by_type(node, "formal_parameters")
        if params_node:
            parameters = self._extract_parameters(params_node, source)
        return_type = None
        type_annotation_node = self._find_child_by_type(
            node,
            "type_annotation",
        )
        if type_annotation_node:
            return_type = (
                self._get_node_text(
                    type_annotation_node,
                    source,
                )
                .strip(":")
                .strip()
            )
        decorators = []
        if node.parent and node.parent.type == "decorator":
            decorator_text = self._get_node_text(node.parent, source).strip(
                "@",
            )
            decorators.append(decorator_text)
        modifiers = []
        if self._has_async_modifier(node, source):
            modifiers.append("async")
        if node.type == "generator_function_declaration" or self._is_generator(
            node,
            source,
        ):
            modifiers.append("generator")
        if node.type == "method_definition":
            for child in node.children:
                if child.type in {
                    "static",
                    "private",
                    "public",
                    "protected",
                    "readonly",
                }:
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
        comment = self._extract_leading_comment(node, source)
        if comment and comment.strip().startswith("/**"):
            return self._clean_jsdoc_comment(comment)
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract import statements used within a node."""
        imports = []

        def collect_imports(n: Node, _depth: int):
            if n.type in {"import_statement", "import_clause"}:
                imports.append(self._get_node_text(n, source).strip())
            elif n.type == "call_expression":
                func_node = self._find_child_by_type(n, "identifier")
                if (
                    func_node
                    and self._get_node_text(
                        func_node,
                        source,
                    )
                    == "require"
                ):
                    imports.append(self._get_node_text(n, source).strip())

        self._walk_tree(node, collect_imports)
        return imports

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk depends on."""
        dependencies = set()
        identifiers = self._extract_identifiers(node, source)
        defined = self._extract_defined_symbols(node, source)
        dependencies = identifiers - defined
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
        if node.type in {"function_declaration", "method_definition"}:
            name_node = self._find_child_by_type(node, "identifier")
            if not name_node and node.type == "method_definition":
                name_node = self._find_child_by_type(node, "property_identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))
        elif node.type == "class_declaration":
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                exports.add(self._get_node_text(name_node, source))
        elif node.type in {"variable_declaration", "lexical_declaration"}:
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = self._find_child_by_type(child, "identifier")
                    if name_node:
                        exports.add(self._get_node_text(name_node, source))
        self._extract_export_symbols(node, source, exports)
        return exports

    def _extract_parameters(
        self,
        params_node: Node,
        source: bytes,
    ) -> list[dict[str, Any]]:
        """Extract parameter information from formal_parameters node."""
        parameters = []
        for child in params_node.children:
            if child.type in {
                "identifier",
                "required_parameter",
                "optional_parameter",
                "rest_parameter",
                "object_pattern",
                "array_pattern",
                "assignment_pattern",
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
        elif param_node.type == "required_parameter":
            pattern_node = self._find_child_by_type(param_node, "identifier")
            if pattern_node:
                param_info["name"] = self._get_node_text(pattern_node, source)
            type_node = self._find_child_by_type(param_node, "type_annotation")
            if type_node:
                param_info["type"] = (
                    self._get_node_text(
                        type_node,
                        source,
                    )
                    .strip(":")
                    .strip()
                )
        elif param_node.type == "optional_parameter":
            pattern_node = self._find_child_by_type(param_node, "identifier")
            if pattern_node:
                param_info["name"] = self._get_node_text(pattern_node, source)
                text = self._get_node_text(param_node, source)
                if "?" in text:
                    param_info["name"] += "?"
            for child in param_node.children:
                if child.type == "=":
                    idx = param_node.children.index(child)
                    if idx + 1 < len(param_node.children):
                        param_info["default"] = self._get_node_text(
                            param_node.children[idx + 1],
                            source,
                        )
        elif param_node.type == "rest_parameter":
            identifier = self._find_child_by_type(param_node, "identifier")
            if identifier:
                param_info["name"] = "..." + self._get_node_text(identifier, source)
        elif param_node.type in {"object_pattern", "array_pattern"}:
            param_info["name"] = self._get_node_text(param_node, source)
        elif param_node.type == "assignment_pattern" and len(param_node.children) >= 3:
            param_info["name"] = self._get_node_text(param_node.children[0], source)
            param_info["default"] = self._get_node_text(param_node.children[2], source)
        return param_info if param_info["name"] else None

    def _has_async_modifier(self, node: Node, source: bytes) -> bool:
        """Check if function has async modifier."""
        if node.parent:
            siblings = node.parent.children
            node_index = siblings.index(node) if node in siblings else -1
            if node_index > 0:
                prev_sibling = siblings[node_index - 1]
                if prev_sibling.type == "async":
                    return True
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

    @staticmethod
    def _clean_jsdoc_comment(comment: str) -> str:
        """Clean JSDoc comment text."""
        lines = comment.strip().split("\n")
        cleaned = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line in {"/**", "*/"}:
                continue
            if stripped_line.startswith("*"):
                stripped_line = stripped_line[1:].strip()
            cleaned.append(stripped_line)
        return "\n".join(cleaned).strip()

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()

        def collect_definitions(n: Node, _depth: int):
            if n.type in {"function_declaration", "class_declaration"}:
                name_node = self._find_child_by_type(n, "identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))
            elif n.type in {"variable_declarator", "const_declaration"}:
                id_node = self._find_child_by_type(n, "identifier")
                if id_node:
                    defined.add(self._get_node_text(id_node, source))
            elif n.type == "formal_parameters":
                for param in n.children:
                    if param.type == "identifier":
                        defined.add(self._get_node_text(param, source))

        self._walk_tree(node, collect_definitions)
        return defined

    def _extract_export_symbols(self, node: Node, source: bytes, exports: set[str]):
        """Extract exported symbols."""

        def collect_exports(n: Node, _depth: int):
            if n.type == "export_statement":
                self._process_export_statement(n, source, exports)

        self._walk_tree(node, collect_exports)

    def _process_export_statement(self, node: Node, source: bytes, exports: set[str]):
        """Process an export statement node."""
        for child in node.children:
            if child.type in {"function_declaration", "class_declaration"}:
                self._add_declared_export(child, source, exports)
            elif child.type == "lexical_declaration":
                self._process_lexical_declaration_exports(child, source, exports)

    def _add_declared_export(self, node: Node, source: bytes, exports: set[str]):
        """Add a function or class declaration export."""
        name_node = self._find_child_by_type(node, "identifier")
        if name_node:
            exports.add(self._get_node_text(name_node, source))

    def _process_lexical_declaration_exports(
        self,
        node: Node,
        source: bytes,
        exports: set[str],
    ):
        """Process exports from lexical declarations."""
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue

            id_node = self._find_child_by_type(declarator, "identifier")
            if id_node:
                exports.add(self._get_node_text(id_node, source))
    
    def extract_calls(self, node: Node, source: bytes) -> list[dict[str, Any]]:
        """Extract function/method calls with their byte spans."""
        calls = []
        
        # Traverse the tree to find all call expressions
        self._extract_calls_recursive(node, source, calls)
        
        return calls
    
    def _extract_calls_recursive(self, node: Node, source: bytes, calls: list) -> None:
        """Recursively extract calls from the AST."""
        if node.type == "call_expression":
            call_info = self._extract_js_call_info(node, source)
            if call_info:
                calls.append(call_info)
        
        # Also handle new expressions (constructor calls)
        elif node.type == "new_expression":
            constructor = self._find_child_by_type(node, "identifier")
            if not constructor:
                # Try member expression for new Foo.Bar()
                constructor = self._find_child_by_type(node, "member_expression")
            
            if constructor:
                name = self._extract_member_name(constructor, source)
                if name:
                    calls.append({
                        "name": f"new {name}",
                        "start": node.start_byte,
                        "end": node.end_byte,
                        "type": "constructor",
                    })
        
        # Also handle tagged template literals (e.g., styled.div`...`)
        elif node.type == "tagged_template_expression":
            tag_node = node.children[0] if node.children else None
            if tag_node:
                name = self._extract_member_name(tag_node, source)
                if name:
                    calls.append({
                        "name": name,
                        "start": node.start_byte,
                        "end": node.end_byte,
                        "type": "tagged_template",
                    })
        
        # Recurse into children
        for child in node.children:
            self._extract_calls_recursive(child, source, calls)
    
    def _extract_js_call_info(self, call_node: Node, source: bytes) -> dict[str, Any] | None:
        """Extract information from a JavaScript call expression."""
        func_node = call_node.children[0] if call_node.children else None
        if not func_node:
            return None
        
        # Extract the function name
        name = None
        call_type = "function"
        
        if func_node.type == "identifier":
            name = self._get_node_text(func_node, source)
        elif func_node.type == "member_expression":
            name = self._extract_member_name(func_node, source)
            call_type = "method"
        elif func_node.type == "super":
            name = "super"
            call_type = "super"
        
        if not name:
            return None
        
        return {
            "name": name,
            "start": call_node.start_byte,
            "end": call_node.end_byte,
            "type": call_type,
        }
    
    def _extract_member_name(self, member_node: Node, source: bytes) -> str | None:
        """Extract the full name from a member expression."""
        if member_node.type == "identifier":
            return self._get_node_text(member_node, source)
        
        if member_node.type != "member_expression":
            return None
        
        parts = []
        current = member_node
        
        while current and current.type == "member_expression":
            # Get the property name
            property_node = None
            for child in current.children:
                if child.type == "property_identifier":
                    property_node = child
                    break
                elif child.type == "identifier" and child != current.children[0]:
                    property_node = child
                    break
            
            if property_node:
                parts.insert(0, self._get_node_text(property_node, source))
            
            # Move to the object part
            current = current.children[0] if current.children else None
        
        # Get the base object
        if current and current.type == "identifier":
            parts.insert(0, self._get_node_text(current, source))
        
        return ".".join(parts) if parts else None


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
            "conditional_expression",
            "binary_expression",
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
            "binary_expression": 0,
            "logical_expression": 1,
            "arrow_function": 0,
            "recursive_call": 1,
        }
        return {**base, **js_specific}

    @staticmethod
    def _increases_nesting(node_type: str) -> bool:
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

    @staticmethod
    def _is_comment_line(line: str) -> bool:
        """Check if line is a JavaScript comment."""
        line = line.strip()
        return (
            line.startswith(("//", "/*", "*"))
            or line.endswith(
                "*/",
            )
            or line == "*/"
        )
