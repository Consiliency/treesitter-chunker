"""
Support for Clojure language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class ClojureConfig(LanguageConfig):
    """Language configuration for Clojure."""

    @property
    def language_id(self) -> str:
        return "clojure"

    @property
    def chunk_types(self) -> set[str]:
        """Clojure-specific chunk types."""
        return {
            # Function definitions
            "list_lit",  # Will filter for defn, defn-, def, etc.
            # Macros
            "defmacro",
            # Protocols and types
            "defprotocol",
            "deftype",
            "defrecord",
            "definterface",
            # Multimethods
            "defmulti",
            "defmethod",
            # Namespaces
            "ns_form",
            # Other forms
            "defonce",
            "defstruct",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".clj", ".cljs", ".cljc", ".edn"}

    def __init__(self):
        super().__init__()

        # Add rules for let bindings
        self.add_chunk_rule(
            ChunkRule(
                node_types={"let_form", "letfn_form"},
                include_children=True,
                priority=5,
                metadata={"type": "let_binding"},
            ),
        )

        # Add rules for anonymous functions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"fn_form"},
                include_children=False,
                priority=4,
                metadata={"type": "lambda"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("str_lit")
        self.add_ignore_type("num_lit")


# Register the Clojure configuration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


# Plugin implementation for backward compatibility
class ClojurePlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Clojure language chunking."""

    @property
    def language_name(self) -> str:
        return "clojure"

    @property
    def supported_extensions(self) -> set[str]:
        return {".clj", ".cljs", ".cljc", ".edn"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "list_lit",  # Will filter for specific forms
            "defmacro",
            "defprotocol",
            "deftype",
            "defrecord",
            "definterface",
            "defmulti",
            "defmethod",
            "ns_form",
            "defonce",
            "defstruct",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a Clojure node."""
        # For list literals, check if it's a definition form
        if node.type == "list_lit":
            children = list(node.children)
            if len(children) >= 2:
                first_child = children[0]
                if first_child.type == "sym_lit":
                    form_name = source[
                        first_child.start_byte : first_child.end_byte
                    ].decode("utf-8")
                    # Check if it's a definition form
                    if form_name in {
                        "defn",
                        "defn-",
                        "def",
                        "defmacro",
                        "defprotocol",
                        "deftype",
                        "defrecord",
                        "defmulti",
                        "defmethod",
                    }:
                        # The second child is usually the name
                        name_child = children[1]
                        if name_child.type == "sym_lit":
                            return source[
                                name_child.start_byte : name_child.end_byte
                            ].decode("utf-8")
        # For namespace forms
        elif node.type == "ns_form":
            for child in node.children:
                if (
                    child.type == "sym_lit" and child != node.children[0]
                ):  # Skip 'ns' symbol
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def _is_definition_form(self, node: Node, source: bytes) -> str | None:
        """Check if a list literal is a definition form and return its type."""
        if node.type != "list_lit":
            return None

        children = list(node.children)
        if len(children) >= 2:
            first_child = children[0]
            if first_child.type == "sym_lit":
                form_name = source[
                    first_child.start_byte : first_child.end_byte
                ].decode("utf-8")
                if form_name in {
                    "defn",
                    "defn-",
                    "def",
                    "defmacro",
                    "defprotocol",
                    "deftype",
                    "defrecord",
                    "defmulti",
                    "defmethod",
                    "defonce",
                    "defstruct",
                }:
                    return form_name
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Clojure."""
        chunks = []

        def extract_chunks(n: Node, namespace: str | None = None):
            # Check for namespace forms
            if n.type == "ns_form":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "namespace",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
                namespace = chunk["name"]

            # Check for definition forms
            elif n.type == "list_lit":
                def_type = self._is_definition_form(n, source)
                if def_type:
                    content = source[n.start_byte : n.end_byte].decode(
                        "utf-8",
                        errors="replace",
                    )
                    chunk = {
                        "type": def_type,
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "content": content,
                        "name": self.get_node_name(n, source),
                    }

                    # Add metadata
                    if def_type == "defn":
                        chunk["is_function"] = True
                        chunk["visibility"] = "public"
                    elif def_type == "defn-":
                        chunk["is_function"] = True
                        chunk["visibility"] = "private"
                    elif def_type == "defmacro":
                        chunk["is_macro"] = True
                    elif def_type in {"deftype", "defrecord"}:
                        chunk["is_type"] = True
                    elif def_type == "defprotocol":
                        chunk["is_protocol"] = True

                    if namespace:
                        chunk["namespace"] = namespace

                    chunks.append(chunk)

            # Regular chunk types
            elif n.type in self.default_chunk_types:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if namespace:
                    chunk["namespace"] = namespace
                chunks.append(chunk)

            # Continue traversal
            for child in n.children:
                extract_chunks(child, namespace)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Clojure-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # Check list literals for definition forms
        if node.type == "list_lit":
            # Need access to source to check form type
            # This is a limitation - we'll handle in process_node
            return True
        # All other chunk types
        if node.type in self.default_chunk_types:
            return True
        # Let forms with substantial content
        if node.type in {"let_form", "letfn_form"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type == "list_lit":
            def_type = self._is_definition_form(node, source)
            if def_type:
                if name:
                    return f"({def_type} {name})"
                return f"({def_type})"
        elif node.type == "ns_form":
            return f"(ns {name})" if name else "(ns)"
        elif node.type == "defprotocol":
            return f"(defprotocol {name})" if name else "(defprotocol)"
        elif node.type == "deftype":
            return f"(deftype {name})" if name else "(deftype)"
        elif node.type == "defrecord":
            return f"(defrecord {name})" if name else "(defrecord)"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process Clojure nodes with special handling for S-expressions."""
        # Handle list literals that are definition forms
        if node.type == "list_lit":
            def_type = self._is_definition_form(node, source)
            if def_type:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk:
                    chunk.node_type = def_type
                    # Add metadata based on definition type
                    chunk.metadata = {"definition_type": def_type}
                    if def_type == "defn-":
                        chunk.metadata["visibility"] = "private"
                    elif def_type == "defn":
                        chunk.metadata["visibility"] = "public"
                    return chunk if self.should_include_chunk(chunk) else None
            else:
                # Not a definition form, skip
                return None

        # Handle let and letfn forms
        if node.type in {"let_form", "letfn_form"}:
            # Only chunk if complex enough
            if len(node.children) > 3:
                chunk = self.create_chunk(node, source, file_path, parent_context)
                if chunk and self.should_include_chunk(chunk):
                    chunk.node_type = node.type
                    return chunk

        # Handle anonymous functions
        if node.type == "fn_form":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                chunk.node_type = "anonymous_function"
                return chunk

        # Default processing
        return super().process_node(node, source, file_path, parent_context)
