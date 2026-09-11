"""Base metadata extraction implementation."""

from abc import ABC

from tree_sitter import Node

from chunker.interfaces.metadata import MetadataExtractor


class BaseMetadataExtractor(MetadataExtractor, ABC):
    """Base implementation for metadata extraction."""

    def __init__(self, language: str):
        """Initialize the metadata extractor.

        Args:
            language: Programming language name
        """
        self.language = language

    def extract_calls(self, node: Node, source: bytes) -> list[dict]:
        """Extract function calls from the AST node."""
        calls = []

        def collect_calls(n: Node, _depth: int):
            if self.language == "dart" and n.type == "selector":
                if n.named_children and n.named_children[0].type == "argument_part":
                    callee = n.prev_named_sibling
                    if callee is not None and n.parent is not None:
                        info = self._extract_call_info(n.parent, callee, source)
                        if info:
                            info.update(
                                start=callee.start_byte,
                                end=n.end_byte,
                                arguments_start=n.start_byte,
                                arguments_end=n.end_byte,
                            )
                            calls.append(info)
                return
            # Handle call expressions across multiple languages
            if n.type in {
                "call",  # Python
                "call_expression",  # JavaScript, Rust, C/C++, Go
                "invocation_expression",  # C#
                "function_call",  # Some languages
                "method_call",  # Some languages
                "macro_invocation",  # Rust: println!("hello")
                "method_invocation",  # Java
                "function_call_expression",  # PHP
                "member_call_expression",  # PHP
                "scoped_call_expression",  # PHP
                "application_expression",  # OCaml
                "apply",  # Haskell
                "list_lit",  # Clojure
            }:
                if n.named_children:
                    func_node: Node | None = (
                        n.child_by_field_name("function")
                        or n.child_by_field_name("method")
                        or n.child_by_field_name("name")
                        or n.child_by_field_name("target")
                        or n.named_children[0]
                    )
                    if self.language == "clojure" and n.type == "list_lit":
                        func_node = self._clojure_callee(n, source)
                    if n.type == "apply":
                        func_node = n.child_by_field_name("function")
                        if func_node is None:  # Type application, not a call.
                            return
                        if n.parent and n.parent.child_by_field_name("function") == n:
                            return
                        while func_node.type == "apply":
                            func_node = func_node.child_by_field_name("function")
                            if func_node is None:
                                return
                    if func_node is not None:
                        call_info = self._extract_call_info(n, func_node, source)
                        if call_info:
                            calls.append(call_info)

        self._walk_tree(node, collect_calls)
        return calls

    def _clojure_callee(self, node: Node, source: bytes) -> Node | None:
        values = node.children_by_field_name("value")
        if not values:
            return None
        callee = values[0]
        if self._clojure_symbol_text(callee, source) in {
            "def",
            "if",
            "do",
            "let",
            "let*",
            "quote",
            "var",
            "fn",
            "fn*",
            "loop",
            "loop*",
            "recur",
            "throw",
            "try",
            "catch",
            "finally",
            "monitor-enter",
            "monitor-exit",
            ".",
            "new",
            "set!",
            "deftype*",
            "reify*",
            "case*",
            "import*",
        }:
            return None
        ancestors = []
        ancestor = node.parent
        while ancestor is not None:
            ancestors.append(ancestor)
            ancestor = ancestor.parent
        syntax_depth = 0
        for ancestor in reversed(ancestors):
            if ancestor.type == "dis_expr":
                return None
            if ancestor.type == "syn_quoting_lit":
                syntax_depth += 1
            elif ancestor.type in {"unquoting_lit", "unquote_splicing_lit"}:
                operand = ancestor.child_by_field_name("value")
                if operand is not None and not (
                    operand.start_byte <= node.start_byte
                    and node.end_byte <= operand.end_byte
                ):
                    return None
                syntax_depth = max(0, syntax_depth - 1)
            elif (syntax_depth == 0 and ancestor.type == "quoting_lit") or (
                self._clojure_ignored_metadata(ancestor, node, source, syntax_depth)
            ):
                return None
            elif ancestor.type == "list_lit":
                values = ancestor.children_by_field_name("value")
                head = self._clojure_symbol_text(values[0], source) if values else ""
                if syntax_depth and head in {
                    "clojure.core/unquote",
                    "clojure.core/unquote-splicing",
                }:
                    if len(values) < 2 or not (
                        values[1].start_byte <= node.start_byte
                        and node.end_byte <= values[1].end_byte
                    ):
                        return None
                    syntax_depth -= 1
                elif syntax_depth == 0 and head == "quote":
                    return None
        return callee if syntax_depth == 0 else None

    def _clojure_symbol_text(self, node: Node, source: bytes) -> str:
        name = node.child_by_field_name("name")
        if node.type != "sym_lit" or name is None:
            return ""
        text = self._get_node_text(name, source)
        namespace = node.child_by_field_name("namespace")
        if namespace is not None:
            text = self._get_node_text(namespace, source) + "/" + text
        return text

    def _clojure_ignored_metadata(
        self, node: Node, call: Node, source: bytes, syntax_depth: int
    ) -> bool:
        target = node.parent
        if target is None or node not in target.children_by_field_name("meta"):
            return False
        keys = set()
        retained_key = None
        for annotation in target.children_by_field_name("meta"):
            value = annotation.child_by_field_name("value")
            if value is None:
                continue
            if value.type == "map_lit":
                entries = value.children_by_field_name("value")
                pairs = [
                    (self._get_node_text(key, source), key, item)
                    for key, item in zip(entries[::2], entries[1::2])
                ]
            else:
                key = (
                    self._get_node_text(value, source)
                    if value.type == "kwd_lit"
                    else ":param-tags" if value.type == "vec_lit" else ":tag"
                )
                pairs = [(key, value, value)]
            for key, key_node, item in pairs:
                if key in keys:
                    continue
                keys.add(key)
                if annotation == node and any(
                    part.start_byte <= call.start_byte
                    and call.end_byte <= part.end_byte
                    for part in (key_node, item)
                ):
                    retained_key = key
        if retained_key is None or (syntax_depth and keys <= {":line", ":column"}):
            return True
        if syntax_depth:
            return False
        if target.type == "list_lit":
            return bool(target.children_by_field_name("value"))
        if target.type != "sym_lit":
            return self._clojure_binding_metadata(target, source, retained_key)
        form = target.parent
        values = (
            form.children_by_field_name("value")
            if form is not None and form.type == "list_lit"
            else []
        )
        head = self._clojure_symbol_text(values[0], source) if values else ""
        head = head.removeprefix("clojure.core/")
        if head == "declare" and target in values[1:]:
            return False
        declarations = {"def", "defn", "defn-", "defmacro", "defonce"}
        return not (head in declarations and len(values) > 1 and target == values[1])

    def _clojure_binding_metadata(
        self, target: Node, source: bytes, metadata_key: str
    ) -> bool:
        functions = {"fn", "fn*", "defn", "defn-", "defmacro"}
        bindings = {"let", "let*", "loop", "loop*", "binding", "with-open"}
        ancestor = target.parent
        while ancestor is not None:
            values = ancestor.children_by_field_name("value")
            if ancestor.type == "list_lit" and values:
                head = self._clojure_symbol_text(values[0], source).removeprefix(
                    "clojure.core/"
                )
                params = None
                function_head = head
                if head in functions:
                    params = next((v for v in values[1:] if v.type == "vec_lit"), None)
                elif values[0].type == "vec_lit" and ancestor.parent is not None:
                    outer = ancestor.parent.children_by_field_name("value")
                    outer_head = (
                        self._clojure_symbol_text(outer[0], source).removeprefix(
                            "clojure.core/"
                        )
                        if outer
                        else ""
                    )
                    if (
                        ancestor.parent.type == "list_lit"
                        and outer_head in functions
                        and not any(v.type == "vec_lit" for v in outer[1:])
                    ):
                        params = values[0]
                        function_head = outer_head
                if params is not None and self._clojure_pattern_metadata(
                    params, target, source
                ):
                    if (
                        params == target
                        and function_head != "fn*"
                        and metadata_key in {":pre", ":post"}
                    ):
                        body = values[values.index(params) + 1 :]
                        return len(body) > 1 and body[0].type == "map_lit"
                    return True
                if head in bindings and len(values) > 1 and values[1].type == "vec_lit":
                    vector = values[1]
                    if vector == target or any(
                        self._clojure_pattern_metadata(pattern, target, source)
                        for pattern in vector.children_by_field_name("value")[::2]
                    ):
                        return True
            ancestor = ancestor.parent
        return False

    def _clojure_pattern_metadata(
        self, pattern: Node, target: Node, source: bytes
    ) -> bool:
        if pattern == target:
            return True
        if not (
            pattern.start_byte <= target.start_byte
            and target.end_byte <= pattern.end_byte
        ):
            return False
        values = pattern.children_by_field_name("value")
        if pattern.type == "vec_lit":
            return any(
                self._clojure_pattern_metadata(value, target, source)
                for value in values
            )
        if pattern.type == "map_lit":
            for key, value in zip(values[::2], values[1::2]):
                keyword = self._get_node_text(key, source)
                if key.type == "kwd_lit" and keyword == ":or":
                    if value == target:
                        return True
                elif key.type == "kwd_lit" and keyword.rsplit("/", 1)[-1].lstrip(
                    ":"
                ) in {
                    "keys",
                    "syms",
                    "strs",
                    "as",
                }:
                    if self._clojure_pattern_metadata(value, target, source):
                        return True
                elif self._clojure_pattern_metadata(key, target, source):
                    return True
        return False

    def _extract_call_info(
        self,
        call_node: Node,
        func_node: Node,
        source: bytes,
    ) -> dict | None:
        """Extract call information from a call node."""
        if func_node.type in {"identifier", "simple_identifier", "name", "variable"}:
            # Simple function call: func()
            return self._create_call_info(call_node, func_node, source)
        if func_node.type in {
            "qualified_identifier",
            "member_access_expression",
            "navigation_expression",
            "dot",
            "value_path",
            "sym_lit",
            "selector",
        }:
            identifiers = []
            self._collect_identifiers_recursive(func_node, identifiers, source)
            if identifiers:
                return self._create_call_info(
                    call_node, func_node, source, identifiers[-1]
                )
        if func_node.type in {
            "member_expression",  # JavaScript, C++
            "attribute",  # Python
            "subscript_expression",  # JavaScript
            "field_expression",  # Rust
            "selector_expression",  # Go
        }:
            # Method call: obj.method() or obj[prop]()
            # For Go selector_expression, always treat as function call
            # For Rust field_expression, always treat as function call (it's method calls)
            # For other member types, we need to be more permissive to catch method calls

            # Check if this is actually a method call by looking at the parent
            is_method_call = False
            if call_node.parent:
                # If parent is a call expression, this is likely a method call
                if call_node.parent.type in {
                    "call",
                    "call_expression",
                    "invocation_expression",
                    "function_call",
                    "method_call",
                    "macro_invocation",
                    "method_invocation",
                    "scoped_call_expression",
                }:
                    is_method_call = True

            # Also check if the call node has arguments
            has_args = False
            for child in call_node.children:
                if child.type in {"argument_list", "arguments", "parameters"}:
                    has_args = True
                    break

            # If it has arguments or is in a call context, treat as method call
            if is_method_call or has_args:
                func_name = self._extract_member_name(func_node, source)
                if func_name:
                    # Enhanced filtering for C member access
                    func_node_text = self._get_node_text(func_node, source)
                    if "->" in func_node_text:
                        # Check if this is actually a method call (has arguments) vs property access
                        if has_args:
                            # obj->method() - this is a method call, don't filter
                            pass
                        else:
                            # obj->field - this is property access, filter it
                            return None
                    return self._create_call_info(
                        call_node,
                        func_node,
                        source,
                        func_name,
                    )

        return None

    def _create_call_info(
        self,
        call_node: Node,
        func_node: Node,
        source: bytes,
        func_name: str | None = None,
    ) -> dict:
        """Create standardized call information."""
        if func_name is None:
            func_name = self._get_node_text(func_node, source)

        return {
            "name": func_name,
            "start": call_node.start_byte,
            "end": call_node.end_byte,
            "function_start": func_node.start_byte,
            "function_end": func_node.end_byte,
            "arguments_start": func_node.end_byte,
            "arguments_end": call_node.end_byte,
        }

    def _extract_member_name(self, node: Node, source: bytes) -> str | None:
        """Extract the rightmost identifier from a member expression."""
        if node.type == "identifier":
            return self._get_node_text(node, source)
        if node.type in {
            "member_expression",  # JavaScript, C++
            "subscript_expression",  # JavaScript
            "attribute",  # Python
            "field_expression",  # Rust
            "selector_expression",  # Go
        }:
            # Walk to the RIGHTMOST identifier (the actual method name)
            # This handles: obj.method, fmt.Println, etc.
            identifiers = []
            self._collect_identifiers_recursive(node, identifiers, source)
            return identifiers[-1] if identifiers else None
        return None

    def _collect_identifiers_recursive(
        self,
        node: Node,
        identifiers: list[str],
        source: bytes,
    ):
        """Recursively collect all identifiers in order (left to right)."""
        if node.type in {
            "identifier",
            "property_identifier",
            "field_identifier",
            "name",
            "simple_identifier",
            "value_name",
            "sym_name",
        }:
            identifiers.append(self._get_node_text(node, source))
        for child in node.children:
            self._collect_identifiers_recursive(child, identifiers, source)

    def _is_actual_function_call(self, call_node: Node, func_node: Node) -> bool:
        """Check if this is actually a function call vs property access."""
        # For backward compatibility, delegate to the new filtering system
        return not self._should_filter_call(
            func_node,
            b"",
        )  # Empty source for compatibility

    def _should_filter_call(self, func_node: Node, source: bytes) -> bool:
        """Enhanced filtering for different languages to distinguish method calls from property access."""
        func_node_text = self._get_node_text(func_node, source)

        # C/C++ member access filtering
        if "->" in func_node_text:
            return True  # Filter out C member access

        return False  # Default: don't filter

    def _walk_tree(self, node: Node, callback, depth: int = 0):
        """Walk the AST tree and call the callback for each node."""
        callback(node, depth)
        for child in node.children:
            self._walk_tree(child, callback, depth + 1)

    def _get_node_text(self, node: Node, source: bytes) -> str:
        """Get the text content of a node from the source."""
        return source[node.start_byte : node.end_byte].decode("utf-8")

    def _is_comment_node(self, node: Node) -> bool:
        """Check if a node is a comment."""
        return node.type in {"comment", "line_comment", "block_comment"}

    @staticmethod
    def _find_child_by_type(node: Node, node_type: str) -> Node | None:
        """Find first child node of specific type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    @staticmethod
    def _find_all_children_by_type(node: Node, node_type: str) -> list[Node]:
        """Find all child nodes of specific type."""
        return [child for child in node.children if child.type == node_type]

    def _extract_identifiers(self, node: Node, source: bytes) -> set[str]:
        """Extract all identifiers from a node."""
        identifiers = set()

        def collect_identifiers(n: Node, _depth: int):
            if n.type == "identifier":
                identifiers.add(self._get_node_text(n, source))

        self._walk_tree(node, collect_identifiers)
        return identifiers

    def _extract_leading_comment(self, node: Node, source: bytes) -> str | None:
        """Extract comment immediately before a node."""
        prev_sibling = node.prev_sibling
        if prev_sibling is not None and self._is_comment_node(prev_sibling):
            return self._get_node_text(prev_sibling, source)
        return None

    def get_docstring(self, node: Node, source: bytes) -> str | None:
        """Get the docstring for a function or class."""
        # Look for docstring in the first child (usually a string literal)
        if node.children:
            first_child = node.children[0]
            if first_child.type in {"string", "string_literal", "comment"}:
                return self._get_node_text(first_child, source)

        # Look for docstring in the previous sibling (for languages like Python)
        if node.prev_sibling:
            prev_sibling = node.prev_sibling
            if self._is_comment_node(prev_sibling):
                return self._get_node_text(prev_sibling, source)
        return None
