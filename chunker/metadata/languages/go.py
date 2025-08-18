"""Go-specific metadata extraction."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo
from chunker.metadata.extractor import BaseMetadataExtractor


class GoMetadataExtractor(BaseMetadataExtractor):
    """Go-specific metadata extraction implementation."""

    def __init__(self, language: str = "go"):
        """Initialize the Go metadata extractor."""
        super().__init__(language)

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function/method signature information."""
        if node.type not in {"function_declaration", "method_declaration"}:
            return None
        
        name_node = self._find_child_by_type(node, "identifier")
        if not name_node:
            return None
        
        name = self._get_node_text(name_node, source)
        
        parameters = []
        params_node = self._find_child_by_type(node, "parameter_list")
        if params_node:
            parameters = self._extract_parameters(params_node, source)
        
        return_type = None
        # Go can have multiple return types
        result_node = self._find_child_by_type(node, "result")
        if result_node:
            return_type = self._get_node_text(result_node, source).strip("()")
        
        modifiers = []
        # Check if it's a method (has receiver)
        if node.type == "method_declaration":
            receiver_node = self._find_child_by_type(node, "parameter_list")
            if receiver_node:
                modifiers.append("method")
        
        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=[],
            modifiers=modifiers,
        )

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract comment from a node."""
        # Go uses // or /* */ for comments
        comment = self._extract_leading_comment(node, source)
        if comment:
            if comment.startswith("//"):
                return comment.strip("/").strip()
            elif comment.startswith("/*"):
                return comment.strip("/*").strip("*/").strip()
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract import statements."""
        imports = []
        
        def collect_imports(n: Node, _depth: int):
            if n.type == "import_declaration":
                imports.append(self._get_node_text(n, source).strip())
            elif n.type == "import_spec":
                # Individual import within an import block
                import_text = self._get_node_text(n, source).strip()
                if import_text:
                    imports.append(import_text)
        
        self._walk_tree(node, collect_imports)
        return imports

    def extract_calls(self, node: Node, source: bytes) -> list[dict[str, Any]]:
        """
        Extract Go-specific function and method calls.
        
        Handles:
        - Function calls: func()
        - Method calls: obj.Method()
        - Package function calls: fmt.Println()
        - Built-in functions: make(), len(), append()
        """
        calls = []
        
        def collect_calls(n: Node, _depth: int):
            # Go uses "call_expression" for function calls
            if n.type == "call_expression":
                func_node = n.children[0] if n.children else None
                if func_node:
                    call_info = self._extract_go_call_info(n, func_node, source)
                    if call_info:
                        calls.append(call_info)
        
        self._walk_tree(node, collect_calls)
        return calls
    
    def _extract_go_call_info(self, call_node: Node, func_node: Node, source: bytes) -> dict[str, Any] | None:
        """Extract Go-specific call information."""
        if func_node.type == "identifier":
            # Simple function call or built-in
            return self._create_call_info(call_node, func_node, source)
        elif func_node.type == "selector_expression":
            # Method call or package function: obj.Method() or fmt.Println()
            # Get the field identifier (method/function name)
            field_node = self._find_child_by_type(func_node, "field_identifier")
            if field_node:
                func_name = self._get_node_text(field_node, source)
                return self._create_call_info(call_node, func_node, source, func_name)
        elif func_node.type == "parenthesized_expression":
            # Function in parentheses: (func)()
            inner_node = func_node.children[1] if len(func_node.children) > 1 else None
            if inner_node:
                return self._extract_go_call_info(call_node, inner_node, source)
        
        return None

    def extract_dependencies(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols that this chunk depends on."""
        dependencies = set()
        identifiers = self._extract_identifiers(node, source)
        defined = self._extract_defined_symbols(node, source)
        dependencies = identifiers - defined
        
        # Filter out Go built-in functions and types
        go_builtins = {
            "append", "cap", "close", "complex", "copy", "delete", "imag", "len",
            "make", "new", "panic", "print", "println", "real", "recover",
            "bool", "byte", "complex64", "complex128", "error", "float32", "float64",
            "int", "int8", "int16", "int32", "int64", "rune", "string",
            "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
            "true", "false", "nil", "iota",
        }
        dependencies = dependencies - go_builtins
        
        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> list[str]:
        """Extract exported symbols."""
        exports = []
        
        # In Go, exported identifiers start with an uppercase letter
        if node.type in {"function_declaration", "method_declaration", "type_declaration", 
                        "const_declaration", "var_declaration"}:
            name_node = self._find_child_by_type(node, "identifier")
            if name_node:
                name = self._get_node_text(name_node, source)
                if name and name[0].isupper():
                    exports.append(name)
        
        # Handle type specs within type declarations
        def collect_type_exports(n: Node, _depth: int):
            if n.type == "type_spec":
                name_node = self._find_child_by_type(n, "type_identifier")
                if name_node:
                    name = self._get_node_text(name_node, source)
                    if name and name[0].isupper():
                        exports.append(name)
        
        self._walk_tree(node, collect_type_exports)
        
        return exports

    def _extract_parameters(self, params_node: Node, source: bytes) -> list[str]:
        """Extract parameter list from a parameter_list node."""
        parameters = []
        for child in params_node.children:
            if child.type == "parameter_declaration":
                param_text = self._get_node_text(child, source)
                parameters.append(param_text)
            elif child.type == "variadic_parameter_declaration":
                param_text = self._get_node_text(child, source)
                parameters.append(param_text)
        return parameters

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()
        
        def collect_definitions(n: Node, _depth: int):
            if n.type == "short_var_declaration":
                # := declarations
                left_node = n.children[0] if n.children else None
                if left_node and left_node.type == "expression_list":
                    for child in left_node.children:
                        if child.type == "identifier":
                            defined.add(self._get_node_text(child, source))
            elif n.type in {"var_spec", "const_spec"}:
                # var and const declarations
                for child in n.children:
                    if child.type == "identifier":
                        defined.add(self._get_node_text(child, source))
            elif n.type in {"function_declaration", "method_declaration"}:
                # Function/method names
                name_node = self._find_child_by_type(n, "identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))
            elif n.type == "type_spec":
                # Type definitions
                name_node = self._find_child_by_type(n, "type_identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))
        
        self._walk_tree(node, collect_definitions)
        return defined