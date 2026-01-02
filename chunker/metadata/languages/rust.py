"""Rust-specific metadata extraction."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo
from chunker.metadata.extractor import BaseMetadataExtractor


class RustMetadataExtractor(BaseMetadataExtractor):
    """Rust-specific metadata extraction implementation."""

    def __init__(self, language: str = "rust"):
        """Initialize the Rust metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function/method signature information."""
        if node.type not in {"function_item", "impl_item"}:
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

        modifiers = []
        visibility_node = self._find_child_by_type(node, "visibility_modifier")
        if visibility_node:
            visibility = self._get_node_text(visibility_node, source)
            if visibility:
                modifiers.append(visibility)

        # Check for async
        for child in node.children:
            if child.type == "async" or (
                child.type == "identifier"
                and self._get_node_text(child, source) == "async"
            ):
                modifiers.append("async")
                break

        # Check for const
        if self._has_const_modifier(node, source):
            modifiers.append("const")

        # Check for unsafe
        if self._has_unsafe_modifier(node, source):
            modifiers.append("unsafe")

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=[],
            modifiers=modifiers,
        )

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract doc comment from a node."""
        # Rust uses /// or //! for doc comments
        comment = self._extract_leading_comment(node, source)
        if comment and (comment.startswith(("///", "//!"))):
            return comment.strip("/").strip()
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract use statements."""
        imports = []

        def collect_imports(n: Node, _depth: int):
            if n.type == "use_declaration":
                imports.append(self._get_node_text(n, source).strip())

        self._walk_tree(node, collect_imports)
        return imports

    def extract_calls(self, node: Node, source: bytes) -> list[dict[str, Any]]:
        """
        Extract Rust-specific function and method calls.

        Handles:
        - Function calls: func()
        - Method calls: obj.method()
        - Associated function calls: Type::function()
        - Macro calls: println!(), vec![]
        """
        calls = []

        def collect_calls(n: Node, _depth: int):
            # Regular function/method calls
            if n.type == "call_expression":
                func_node = n.children[0] if n.children else None
                if func_node:
                    call_info = self._extract_rust_call_info(n, func_node, source)
                    if call_info:
                        calls.append(call_info)

            # Macro calls
            elif n.type == "macro_invocation":
                # Extract macro name
                macro_node = self._find_child_by_type(n, "identifier")
                if not macro_node and n.children:
                    # Sometimes the macro name is in a scoped_identifier
                    for child in n.children:
                        if child.type == "scoped_identifier":
                            # Get the last identifier in the scope
                            identifiers = []
                            self._collect_identifiers_recursive(
                                child,
                                identifiers,
                                source,
                            )
                            if identifiers:
                                macro_name = identifiers[-1]
                                call_info = {
                                    "name": macro_name,
                                    "start": n.start_byte,
                                    "end": n.end_byte,
                                    "function_start": n.start_byte,
                                    "function_end": n.start_byte
                                    + len(macro_name.encode()),
                                    "arguments_start": n.start_byte
                                    + len(macro_name.encode())
                                    + 1,
                                    "arguments_end": n.end_byte,
                                }
                                calls.append(call_info)
                        elif child.type == "identifier":
                            macro_node = child
                            break

                if macro_node:
                    call_info = self._create_call_info(n, macro_node, source)
                    if call_info:
                        calls.append(call_info)

        self._walk_tree(node, collect_calls)
        return calls

    def _extract_rust_call_info(
        self,
        call_node: Node,
        func_node: Node,
        source: bytes,
    ) -> dict[str, Any] | None:
        """Extract Rust-specific call information."""
        if func_node.type == "identifier":
            # Simple function call
            return self._create_call_info(call_node, func_node, source)
        if func_node.type == "field_expression":
            # Method call: obj.method()
            # Get the field identifier (method name)
            field_node = self._find_child_by_type(func_node, "field_identifier")
            if field_node:
                func_name = self._get_node_text(field_node, source)
                return self._create_call_info(call_node, func_node, source, func_name)
        elif func_node.type == "scoped_identifier":
            # Associated function call: Type::function()
            # Get the last identifier in the scope
            identifiers = []
            self._collect_identifiers_recursive(func_node, identifiers, source)
            if identifiers:
                func_name = identifiers[-1]
                return self._create_call_info(call_node, func_node, source, func_name)

        return None

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk depends on."""
        dependencies = set()
        identifiers = self._extract_identifiers(node, source)
        defined = self._extract_defined_symbols(node, source)
        dependencies = identifiers - defined

        # Filter out Rust keywords and common macros
        rust_builtins = {
            "println",
            "print",
            "eprintln",
            "eprint",
            "panic",
            "assert",
            "assert_eq",
            "assert_ne",
            "vec",
            "format",
            "write",
            "writeln",
            "todo",
            "unimplemented",
            "unreachable",
            "dbg",
            "include",
            "include_str",
            "include_bytes",
            "Some",
            "None",
            "Ok",
            "Err",
            "Box",
            "Vec",
            "String",
            "HashMap",
            "HashSet",
            "Option",
            "Result",
            "Default",
            "Clone",
            "Copy",
            "Debug",
            "Display",
        }
        dependencies -= rust_builtins

        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> list[str]:
        """Extract exported symbols."""
        exports = []

        # In Rust, public items are exported
        if node.type in {
            "function_item",
            "struct_item",
            "enum_item",
            "trait_item",
            "impl_item",
        }:
            visibility_node = self._find_child_by_type(node, "visibility_modifier")
            if visibility_node and "pub" in self._get_node_text(
                visibility_node,
                source,
            ):
                name_node = self._find_child_by_type(node, "identifier")
                if name_node:
                    exports.append(self._get_node_text(name_node, source))

        return exports

    def _extract_parameters(self, params_node: Node, source: bytes) -> list[str]:
        """Extract parameter list from a parameters node."""
        parameters = []
        for child in params_node.children:
            if child.type in {"parameter", "self_parameter", "variadic_parameter"}:
                param_text = self._get_node_text(child, source)
                parameters.append(param_text)
        return parameters

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()

        def collect_definitions(n: Node, _depth: int):
            if n.type in {"let_declaration", "const_item", "static_item"}:
                # Variable/constant definitions
                pattern_node = self._find_child_by_type(n, "identifier")
                if pattern_node:
                    defined.add(self._get_node_text(pattern_node, source))
            elif n.type in {"function_item", "struct_item", "enum_item"}:
                # Type/function definitions
                name_node = self._find_child_by_type(n, "identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))

        self._walk_tree(node, collect_definitions)
        return defined

    def _has_const_modifier(self, node: Node, source: bytes) -> bool:
        """Check if node has const modifier."""
        for child in node.children:
            if child.type == "const" or (
                child.type == "identifier"
                and self._get_node_text(child, source) == "const"
            ):
                return True
        return False

    def _has_unsafe_modifier(self, node: Node, source: bytes) -> bool:
        """Check if node has unsafe modifier."""
        for child in node.children:
            if child.type == "unsafe" or (
                child.type == "identifier"
                and self._get_node_text(child, source) == "unsafe"
            ):
                return True
        return False
