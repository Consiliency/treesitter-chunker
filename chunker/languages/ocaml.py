"""
Support for OCaml language.
"""
from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class OCamlConfig(LanguageConfig):
    """Language configuration for OCaml."""

    @property
    def language_id(self) -> str:
        return "ocaml"

    @property
    def chunk_types(self) -> set[str]:
        """OCaml-specific chunk types."""
        return {"value_definition", "let_binding", "let_rec_binding",
            "function_definition", "fun_expression", "type_definition",
            "type_binding", "module_definition", "module_binding",
            "signature", "structure", "exception_definition",
            "class_definition", "class_binding", "comment"}

    @property
    def file_extensions(self) -> set[str]:
        return {".ml", ".mli", ".mll", ".mly"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(ChunkRule(node_types={"match_expression",
            "function_expression"}, include_children=True, priority=5,
            metadata={"type": "pattern_matching"}))
        self.add_ignore_type("string")
        self.add_ignore_type("number")
        self.add_ignore_type("constructor")



# Register the OCaml configuration


class OCamlPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for OCaml language chunking."""

    @property
    def language_name(self) -> str:
        return "ocaml"

    @property
    def supported_extensions(self) -> set[str]:
        return {".ml", ".mli", ".mll", ".mly"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {"value_definition", "let_binding", "let_rec_binding",
            "function_definition", "fun_expression", "type_definition",
            "type_binding", "module_definition", "module_binding",
            "signature", "structure", "exception_definition",
            "class_definition", "class_binding", "comment"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract the name from an OCaml node."""
        if node.type in {"value_definition", "let_binding", "let_rec_binding"}:
            for child in node.children:
                if child.type == "value_name":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
                if child.type == "let_binding":
                    for subchild in child.children:
                        if subchild.type == "value_name":
                            return source[subchild.start_byte:subchild.end_byte
                                ].decode("utf-8")
        elif node.type in {"type_definition", "type_binding"}:
            for child in node.children:
                if child.type in {"type_constructor", "lowercase_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type in {"module_definition", "module_binding"}:
            for child in node.children:
                if child.type in {"module_name", "uppercase_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type == "exception_definition":
            for child in node.children:
                if child.type in {"constructor_name", "uppercase_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type in {"class_definition", "class_binding"}:
            for child in node.children:
                if child.type in {"class_name", "lowercase_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to OCaml."""
        chunks = []

        def extract_chunks(n: Node, module_context: (str | None) = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": n.type, "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                if module_context:
                    chunk["module"] = module_context
                if n.type in {"let_binding", "let_rec_binding"}:
                    chunk["is_recursive"] = n.type == "let_rec_binding"
                elif n.type == "type_definition":
                    if "=" in content and "|" in content:
                        chunk["type_kind"] = "variant"
                    elif "=" in content and "{" in content:
                        chunk["type_kind"] = "record"
                    else:
                        chunk["type_kind"] = "alias"
                chunks.append(chunk)
                if n.type in {"module_definition", "module_binding"}:
                    module_context = self.get_node_name(n, source)
            for child in n.children:
                extract_chunks(child, module_context)
        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get OCaml-specific node types that form chunks."""
        return self.default_chunk_types

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type.endswith("_definition") or node.type.endswith("_binding"):
            return True
        if node.type in {"fun_expression", "function_expression"}:
            return True
        if node.type in {"signature", "structure"}:
            return True
        return node.type == "comment"

    def get_node_context(self, node: Node, source: bytes) -> (str | None):
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)
        if node.type in {"value_definition", "let_binding"}:
            if name:
                return f"let {name}"
            return "let binding"
        if node.type == "let_rec_binding":
            if name:
                return f"let rec {name}"
            return "let rec binding"
        if node.type in {"type_definition", "type_binding"}:
            if name:
                return f"type {name}"
            return "type definition"
        if node.type in {"module_definition", "module_binding"}:
            if name:
                return f"module {name}"
            return "module"
        if node.type == "exception_definition":
            if name:
                return f"exception {name}"
            return "exception"
        if node.type in {"class_definition", "class_binding"}:
            if name:
                return f"class {name}"
            return "class"
        if node.type == "signature":
            return "module signature"
        if node.type == "structure":
            return "module structure"
        return None

    def process_node(self, node: Node, source: bytes, file_path: str,
        parent_context: (str | None) = None):
        """Process OCaml nodes with special handling for nested structures."""
        if node.type in {"module_definition", "module_binding"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                module_name = self.get_node_name(node, source)
                if module_name:
                    parent_context = f"module:{module_name}"
                return chunk
        if node.type == "let_rec_binding":
            chunks = []
            main_chunk = self.create_chunk(node, source, file_path,
                parent_context)
            if main_chunk and self.should_include_chunk(main_chunk):
                chunks.append(main_chunk)
            for child in node.children:
                if child.type == "let_binding":
                    sub_chunk = self.create_chunk(child, source, file_path,
                        parent_context)
                    if sub_chunk and self.should_include_chunk(sub_chunk):
                        sub_chunk.node_type = "recursive_function"
                        chunks.append(sub_chunk)
            return chunks if chunks else None
        if node.type == "type_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk and self.should_include_chunk(chunk):
                content = source[node.start_byte:node.end_byte].decode("utf-8")
                if "|" in content:
                    chunk.metadata = {"type_kind": "variant"}
                elif "{" in content and "}" in content:
                    chunk.metadata = {"type_kind": "record"}
                return chunk
        return super().process_node(node, source, file_path, parent_context)

    def get_context_for_children(self, node: Node, chunk) -> str:
        """Build context string for nested definitions."""
        if node.type in {"module_definition", "module_binding"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"module:{name}"
        if node.type in {"class_definition", "class_binding"}:
            name = self.get_node_name(node, chunk.content.encode("utf-8"))
            if name:
                return f"class:{name}"
        return chunk.node_type
