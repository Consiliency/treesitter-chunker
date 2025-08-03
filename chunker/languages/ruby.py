"""Ruby language support for chunking."""
from tree_sitter import Node

from chunker.types import CodeChunk

from .base import LanguageChunker


class RubyChunker(LanguageChunker):
    """Chunker implementation for Ruby."""

    @property
    def language_name(self) -> str:
        """Get the language name."""
        return "ruby"

    @property
    def file_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".rb", ".rake", ".gemspec", ".ru"]

    @staticmethod
    def get_chunk_node_types() -> set[str]:
        """Get node types that should be chunked."""
        return {"method", "singleton_method", "class", "module",
            "singleton_class", "block", "lambda", "assignment", "call"}

    @staticmethod
    def get_scope_node_types() -> set[str]:
        """Get node types that define scopes."""
        return {"program", "class", "module", "method", "singleton_method",
            "block", "lambda", "if", "unless", "case", "while", "until",
            "for", "begin"}

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a node should be chunked."""
        if node.type not in self.get_chunk_node_types():
            return False
        if node.type == "block":
            parent = node.parent
            if parent and parent.type == "call":
                method_name = self._get_call_method_name(parent)
                if method_name in {"describe", "context", "it", "before",
                    "after", "namespace", "resources", "scope", "task"}:
                    return True
            return False
        if node.type == "call":
            method_name = self._get_call_method_name(node)
            return method_name in {"attr_accessor", "attr_reader",
                "attr_writer"}
        return not (node.type in {"method", "lambda"} and not self.
            _has_name(node))

    def extract_chunk_info(self, node: Node, _source_code: bytes) -> dict:
        """Extract additional information for a chunk."""
        info = {}
        if node.type == "method":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["method_name"] = name_node.text.decode("utf-8")
            info["visibility"] = self._get_method_visibility(node)
        elif node.type == "class":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["class_name"] = name_node.text.decode("utf-8")
            superclass_node = node.child_by_field_name("superclass")
            if superclass_node:
                info["superclass"] = superclass_node.text.decode("utf-8")
        elif node.type == "module":
            name_node = node.child_by_field_name("name")
            if name_node:
                info["module_name"] = name_node.text.decode("utf-8")
        elif node.type == "call":
            method_name = self._get_call_method_name(node)
            if method_name in {"attr_accessor", "attr_reader", "attr_writer"}:
                info["attr_type"] = method_name
                info["attributes"] = self._extract_attr_names(node)
        elif node.type == "block":
            parent = node.parent
            if parent and parent.type == "call":
                method_name = self._get_call_method_name(parent)
                info["block_type"] = method_name
                args = self._get_call_arguments(parent)
                if args:
                    info["block_description"] = args[0]
        return info

    @staticmethod
    def get_context_nodes(node: Node) -> list[Node]:
        """Get nodes that provide context for a chunk."""
        context_nodes = []
        current = node.parent
        while current:
            if current.type in {"class", "module"}:
                context_nodes.append(current)
            elif current.type == "program":
                break
            current = current.parent
        return context_nodes

    @staticmethod
    def _has_name(node: Node) -> bool:
        """Check if a node has a name."""
        if node.type == "method":
            name_node = node.child_by_field_name("name")
            return name_node is not None
        if node.type == "lambda":
            return False
        return True

    @staticmethod
    def _get_call_method_name(call_node: Node) -> (str | None):
        """Extract method name from a call node."""
        method_node = call_node.child_by_field_name("method")
        if method_node:
            return method_node.text.decode("utf-8")
        return None

    @staticmethod
    def _get_call_arguments(call_node: Node) -> list[str]:
        """Extract arguments from a call node."""
        args = []
        arguments_node = call_node.child_by_field_name("arguments")
        if arguments_node:
            args.extend(child.text.decode("utf-8").strip('"\'') for child in
                arguments_node.children if child.type in {"string",
                "symbol", "identifier"})
        return args

    @staticmethod
    def _extract_attr_names(attr_call_node: Node) -> list[str]:
        """Extract attribute names from attr_* calls."""
        names = []
        arguments_node = attr_call_node.child_by_field_name("arguments")
        if arguments_node:
            for child in arguments_node.children:
                if child.type == "symbol":
                    name = child.text.decode("utf-8").lstrip(":")
                    names.append(name)
        return names

    def _get_method_visibility(self, method_node: Node) -> str:
        """Determine method visibility (public/private/protected)."""
        if not method_node.parent:
            return "public"
        prev = method_node.prev_sibling
        while prev:
            if prev.type == "call":
                method_name = self._get_call_method_name(prev)
                if method_name in {"private", "protected", "public"}:
                    return method_name
            prev = prev.prev_sibling
        return "public"

    @staticmethod
    def merge_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Merge related chunks."""
        merged = []
        attr_groups = {}
        other_chunks = []
        for chunk in chunks:
            if chunk.metadata.get("attr_type"):
                parent_class = chunk.parent_context
                if parent_class:
                    key = parent_class, chunk.metadata["attr_type"]
                    if key not in attr_groups:
                        attr_groups[key] = []
                    attr_groups[key].append(chunk)
                else:
                    other_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        for (parent_class, attr_type), attr_chunks in attr_groups.items():
            if len(attr_chunks) > 1:
                all_attrs = []
                for chunk in attr_chunks:
                    all_attrs.extend(chunk.metadata.get("attributes", []))
                merged_chunk = attr_chunks[0]
                merged_chunk.metadata["attributes"] = all_attrs
                merged_chunk.content = (
                    f"{attr_type} {', '.join(':' + a for a in all_attrs)}")
                merged.append(merged_chunk)
            else:
                merged.extend(attr_chunks)
        merged.extend(other_chunks)
        return merged
