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
            # Handle call expressions across multiple languages
            if n.type in {
                "call",                    # Python
                "call_expression",         # JavaScript, Rust, C/C++, Go
                "invocation_expression",   # C#
                "function_call",           # Some languages
                "method_call",             # Some languages
                "macro_invocation",        # Rust: println!("hello")
            }:
                if n.children:
                    func_node = n.children[0]
                    call_info = self._extract_call_info(n, func_node, source)
                    if call_info:
                        calls.append(call_info)
            
        self._walk_tree(node, collect_calls)
        return calls

    def _extract_call_info(self, call_node: Node, func_node: Node, source: bytes) -> dict | None:
        """Extract call information from a call node."""
        if func_node.type == "identifier":
            # Simple function call: func()
            return self._create_call_info(call_node, func_node, source)
        elif func_node.type in {
            "member_expression",      # JavaScript, C++
            "attribute",              # Python
            "subscript_expression",   # JavaScript
            "field_expression",       # Rust
            "selector_expression",    # Go
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
                    "call", "call_expression", "invocation_expression", "function_call", 
                    "method_call", "macro_invocation", "method_invocation", "scoped_call_expression"
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
                    return self._create_call_info(call_node, func_node, source, func_name)
        
        return None

    def _create_call_info(self, call_node: Node, func_node: Node, source: bytes, 
                         func_name: str | None = None) -> dict:
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
            "arguments_end": call_node.end_byte
        }

    def _extract_member_name(self, node: Node, source: bytes) -> str | None:
        """Extract the rightmost identifier from a member expression."""
        if node.type == "identifier":
            return self._get_node_text(node, source)
        elif node.type in {
            "member_expression",      # JavaScript, C++
            "subscript_expression",   # JavaScript
            "attribute",              # Python
            "field_expression",       # Rust
            "selector_expression",    # Go
        }:
            # Walk to the RIGHTMOST identifier (the actual method name)
            # This handles: obj.method, fmt.Println, etc.
            identifiers = []
            self._collect_identifiers_recursive(node, identifiers, source)
            return identifiers[-1] if identifiers else None
        return None

    def _collect_identifiers_recursive(self, node: Node, identifiers: list[str], source: bytes):
        """Recursively collect all identifiers in order (left to right)."""
        if node.type in {"identifier", "property_identifier", "field_identifier", "name"}:
            identifiers.append(self._get_node_text(node, source))
        for child in node.children:
            self._collect_identifiers_recursive(child, identifiers, source)

    def _is_actual_function_call(self, call_node: Node, func_node: Node) -> bool:
        """Check if this is actually a function call vs property access."""
        # For backward compatibility, delegate to the new filtering system
        return not self._should_filter_call(func_node, b"")  # Empty source for compatibility

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
        return source[node.start_byte:node.end_byte].decode('utf-8')

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
        if not node.parent:
            return None
        siblings = node.parent.children
        node_index = None
        for i, sibling in enumerate(siblings):
            if sibling == node:
                node_index = i
                break
        if node_index is None or node_index == 0:
            return None
        prev_sibling = siblings[node_index - 1]
        if self._is_comment_node(prev_sibling):
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
