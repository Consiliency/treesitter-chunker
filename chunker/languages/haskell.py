"""
Support for Haskell language.
"""
from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class HaskellConfig(LanguageConfig):
    """Language configuration for Haskell."""

    @property
    def language_id(self) -> str:
        return "haskell"

    @property
    def chunk_types(self) -> set[str]:
        """Haskell-specific chunk types."""
        return {"function", "function_declaration", "function_body",
            "type_alias", "type_synonym", "data_type", "data_constructor",
            "newtype", "class_declaration", "instance_declaration",
            "module_declaration", "import_declaration", "pragma"}

    @property
    def file_extensions(self) -> set[str]:
        return {".hs", ".lhs"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(ChunkRule(node_types={"where_clause"},
            include_children=True, priority=5, metadata={"type":
            "where_bindings"}))
        self.add_chunk_rule(ChunkRule(node_types={"case_expression",
            "guards"}, include_children=False, priority=4, metadata={"type":
            "pattern_matching"}))
        self.add_ignore_type("comment")
        self.add_ignore_type("string")
        self.add_ignore_type("integer")



# Register the Haskell configuration


class HaskellPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for Haskell language chunking."""

    @property
    def language_name(self) -> str:
        return "haskell"

    @property
    def supported_extensions(self) -> set[str]:
        return {".hs", ".lhs"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {"function", "function_declaration", "function_body",
            "type_alias", "type_synonym", "data_type", "data_constructor",
            "newtype", "class_declaration", "instance_declaration",
            "module_declaration"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract the name from a Haskell node."""
        if node.type in {"function", "function_declaration"}:
            for child in node.children:
                if child.type in {"variable", "variable_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type in {"type_alias", "data_type", "newtype"}:
            for child in node.children:
                if child.type in {"type", "type_constructor_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type in {"class_declaration", "instance_declaration"}:
            for child in node.children:
                if child.type in {"class_name", "type_class_identifier"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to Haskell."""
        chunks = []

        def extract_chunks(n: Node, parent_context: (str | None) = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": n.type, "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                if n.type == "function":
                    chunk["is_function"] = True
                    if parent_context == "type_signature":
                        chunk["has_type_signature"] = True
                elif n.type in {"type_alias", "data_type", "newtype"}:
                    chunk["is_type_definition"] = True
                elif n.type in {"class_declaration", "instance_declaration"}:
                    chunk["is_typeclass"] = True
                chunks.append(chunk)
            new_context = n.type if n.type in {"type_signature", "where",
                } else parent_context
            for child in n.children:
                extract_chunks(child, new_context)
        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get Haskell-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type in {"let_bindings", "where"}:
            return len(node.children) > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> (str | None):
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)
        if node.type == "function":
            return f"function {name}" if name else "function"
        if node.type in {"type_alias", "type_synonym"}:
            return f"type {name}" if name else "type alias"
        if node.type == "data_type":
            return f"data {name}" if name else "data type"
        if node.type == "newtype":
            return f"newtype {name}" if name else "newtype"
        if node.type == "class_declaration":
            return f"class {name}" if name else "typeclass"
        if node.type == "instance_declaration":
            return f"instance {name}" if name else "instance"
        if node.type == "module_declaration":
            return "module declaration"
        return None

    def process_node(self, node: Node, source: bytes, file_path: str,
        parent_context: (str | None) = None):
        """Process Haskell nodes with special handling for nested definitions."""
        if node.type == "function" and parent_context != "processed":
            parent = node.parent
            if parent:
                prev_sibling = None
                for i, child in enumerate(parent.children):
                    if child == node and i > 0:
                        prev_sibling = parent.children[i - 1]
                        break
                if prev_sibling and prev_sibling.type == "type_signature":
                    combined_start = prev_sibling.start_byte
                    combined_end = node.end_byte
                    combined_content = source[combined_start:combined_end
                        ].decode("utf-8", errors="replace")
                    chunk = self.create_chunk(node, source, file_path,
                        parent_context)
                    if chunk:
                        chunk.content = combined_content
                        chunk.start_line = prev_sibling.start_point[0] + 1
                        chunk.byte_start = combined_start
                        chunk.node_type = "function_with_signature"
                        return chunk if self.should_include_chunk(chunk,
                            ) else None
        if node.type == "where" and any(child.type in {"function",
            "function_declaration"} for child in node.children):
            return super().process_node(node, source, file_path, parent_context,
                )
        return super().process_node(node, source, file_path, parent_context)
