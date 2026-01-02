"""C/C++-specific metadata extraction."""

from typing import Any

from tree_sitter import Node

from chunker.interfaces.metadata import SignatureInfo
from chunker.metadata.extractor import BaseMetadataExtractor


class CMetadataExtractor(BaseMetadataExtractor):
    """C/C++-specific metadata extraction implementation."""

    def __init__(self, language: str = "c"):
        """Initialize the C/C++ metadata extractor."""
        super().__init__(language)
        self.is_cpp = language == "cpp"

    def extract_signature(self, node: Node, source: bytes) -> SignatureInfo | None:
        """Extract function signature information."""
        if node.type not in {"function_definition", "function_declarator"}:
            return None

        # Find the declarator which contains the function name
        declarator = node
        if node.type == "function_definition":
            declarator = self._find_child_by_type(node, "function_declarator")
            if not declarator:
                # Sometimes it's a pointer_declarator containing a function_declarator
                pointer_decl = self._find_child_by_type(node, "pointer_declarator")
                if pointer_decl:
                    declarator = self._find_child_by_type(
                        pointer_decl,
                        "function_declarator",
                    )

        if not declarator:
            return None

        # Extract function name
        name = None
        for child in declarator.children:
            if child.type == "identifier" or child.type == "field_identifier":
                name = self._get_node_text(child, source)
                break

        if not name:
            return None

        # Extract parameters
        parameters = []
        params_node = self._find_child_by_type(declarator, "parameter_list")
        if params_node:
            parameters = self._extract_parameters(params_node, source)

        # Extract return type
        return_type = None
        if node.type == "function_definition":
            # Return type is usually before the declarator
            for i, child in enumerate(node.children):
                if child == declarator or (
                    child.type == "pointer_declarator"
                    and declarator in self._get_all_descendants(child)
                ):
                    # Get all nodes before the declarator as return type
                    if i > 0:
                        return_type_nodes = node.children[:i]
                        return_type = " ".join(
                            self._get_node_text(n, source) for n in return_type_nodes
                        ).strip()
                    break

        modifiers = []
        # Check for static, inline, etc.
        if node.type == "function_definition":
            for child in node.children:
                if child.type == "storage_class_specifier" or child.type in {
                    "type_qualifier",
                    "inline",
                }:
                    modifier = self._get_node_text(child, source)
                    if modifier:
                        modifiers.append(modifier)

        return SignatureInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            decorators=[],
            modifiers=modifiers,
        )

    def extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract comment from a node."""
        # C/C++ uses // or /* */ for comments
        comment = self._extract_leading_comment(node, source)
        if comment:
            if comment.startswith("//"):
                return comment.strip("/").strip()
            if comment.startswith("/*"):
                return comment.strip("/*").strip("*/").strip()
        return None

    def extract_imports(self, node: Node, source: bytes) -> list[str]:
        """Extract include statements."""
        imports = []

        def collect_imports(n: Node, _depth: int):
            if n.type == "preproc_include":
                imports.append(self._get_node_text(n, source).strip())

        self._walk_tree(node, collect_imports)
        return imports

    def extract_calls(self, node: Node, source: bytes) -> list[dict[str, Any]]:
        """
        Extract C/C++-specific function calls.

        Handles:
        - Function calls: func()
        - Method calls (C++): obj.method(), obj->method()
        - Function pointer calls: (*func_ptr)()
        - Macro calls: MACRO()
        """
        calls = []

        def collect_calls(n: Node, _depth: int):
            # C/C++ uses "call_expression" for function calls
            if n.type == "call_expression":
                func_node = n.children[0] if n.children else None
                if func_node:
                    call_info = self._extract_c_call_info(n, func_node, source)
                    if call_info:
                        calls.append(call_info)

        self._walk_tree(node, collect_calls)
        return calls

    def _extract_c_call_info(
        self,
        call_node: Node,
        func_node: Node,
        source: bytes,
    ) -> dict[str, Any] | None:
        """Extract C/C++-specific call information."""
        if func_node.type == "identifier":
            # Simple function call or macro
            return self._create_call_info(call_node, func_node, source)
        if func_node.type == "field_expression":
            # Method call: obj.method() or obj->method()
            field_node = self._find_child_by_type(func_node, "field_identifier")
            if field_node:
                func_name = self._get_node_text(field_node, source)
                return self._create_call_info(call_node, func_node, source, func_name)
        elif func_node.type == "parenthesized_expression":
            # Function pointer call: (*func_ptr)()
            inner_node = func_node.children[1] if len(func_node.children) > 1 else None
            if inner_node:
                if inner_node.type == "pointer_expression":
                    # Dereference pointer
                    ptr_node = inner_node.children[-1] if inner_node.children else None
                    if ptr_node and ptr_node.type == "identifier":
                        func_name = self._get_node_text(ptr_node, source)
                        return self._create_call_info(
                            call_node,
                            func_node,
                            source,
                            func_name,
                        )
                return self._extract_c_call_info(call_node, inner_node, source)
        elif func_node.type == "qualified_identifier" and self.is_cpp:
            # C++ qualified calls: namespace::function()
            # Get the last identifier
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

        # Filter out C standard library functions and macros
        c_builtins = {
            "printf",
            "scanf",
            "fprintf",
            "fscanf",
            "sprintf",
            "sscanf",
            "malloc",
            "calloc",
            "realloc",
            "free",
            "exit",
            "abort",
            "strlen",
            "strcpy",
            "strncpy",
            "strcmp",
            "strncmp",
            "strcat",
            "memcpy",
            "memmove",
            "memset",
            "memcmp",
            "fopen",
            "fclose",
            "fread",
            "fwrite",
            "fgetc",
            "fputc",
            "NULL",
            "EOF",
            "stdin",
            "stdout",
            "stderr",
            "size_t",
            "FILE",
            "void",
            "int",
            "char",
            "float",
            "double",
            "long",
            "short",
            "unsigned",
            "signed",
            "const",
            "static",
        }

        if self.is_cpp:
            # Add C++ specific builtins
            cpp_builtins = {
                "std",
                "cout",
                "cin",
                "cerr",
                "endl",
                "string",
                "vector",
                "map",
                "set",
                "list",
                "queue",
                "stack",
                "deque",
                "unique_ptr",
                "shared_ptr",
                "weak_ptr",
                "make_unique",
                "make_shared",
                "new",
                "delete",
                "nullptr",
                "true",
                "false",
                "bool",
                "namespace",
                "class",
                "template",
                "typename",
                "auto",
            }
            c_builtins |= cpp_builtins

        dependencies -= c_builtins

        return dependencies

    def extract_exports(self, node: Node, source: bytes) -> list[str]:
        """Extract exported symbols."""
        exports = []

        # In C, functions not marked static are exported
        # In C++, we also need to consider class members
        if node.type == "function_definition":
            # Check if it's static
            is_static = False
            for child in node.children:
                if child.type == "storage_class_specifier":
                    if "static" in self._get_node_text(child, source):
                        is_static = True
                        break

            if not is_static:
                sig = self.extract_signature(node, source)
                if sig and sig.name:
                    exports.append(sig.name)

        return exports

    def _extract_parameters(self, params_node: Node, source: bytes) -> list[str]:
        """Extract parameter list from a parameter_list node."""
        parameters = []
        for child in params_node.children:
            if child.type in {"parameter_declaration", "variadic_parameter"}:
                param_text = self._get_node_text(child, source)
                if param_text and param_text not in {"(", ")", ","}:
                    parameters.append(param_text)
        return parameters

    def _extract_defined_symbols(self, node: Node, source: bytes) -> set[str]:
        """Extract symbols defined within this node."""
        defined = set()

        def collect_definitions(n: Node, _depth: int):
            if n.type == "declaration":
                # Variable declarations
                declarators = self._find_all_declarators(n)
                for decl in declarators:
                    if decl.type == "identifier":
                        defined.add(self._get_node_text(decl, source))
            elif n.type == "function_definition":
                # Function definitions
                sig = self.extract_signature(n, source)
                if sig and sig.name:
                    defined.add(sig.name)
            elif n.type in {"struct_specifier", "union_specifier", "enum_specifier"}:
                # Type definitions
                name_node = self._find_child_by_type(n, "type_identifier")
                if name_node:
                    defined.add(self._get_node_text(name_node, source))

        self._walk_tree(node, collect_definitions)
        return defined

    def _find_all_declarators(self, node: Node) -> list[Node]:
        """Find all declarators in a declaration node."""
        declarators = []

        def find_declarators(n: Node):
            if n.type in {
                "init_declarator",
                "declarator",
                "pointer_declarator",
                "array_declarator",
                "function_declarator",
            }:
                # Look for identifier within declarator
                for child in n.children:
                    if child.type == "identifier":
                        declarators.append(child)
                    else:
                        find_declarators(child)

        for child in node.children:
            find_declarators(child)

        return declarators

    def _get_all_descendants(self, node: Node) -> list[Node]:
        """Get all descendant nodes."""
        descendants = []

        def collect(n: Node):
            descendants.append(n)
            for child in n.children:
                collect(child)

        for child in node.children:
            collect(child)

        return descendants


class CppMetadataExtractor(CMetadataExtractor):
    """C++-specific metadata extraction implementation."""

    def __init__(self, language: str = "cpp"):
        """Initialize the C++ metadata extractor."""
        super().__init__(language="cpp")
