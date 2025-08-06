"""
Support for WebAssembly Text Format (WAT/WASM) language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class WASMConfig(LanguageConfig):
    """Language configuration for WebAssembly Text Format."""

    @property
    def language_id(self) -> str:
        return "wat"

    @property
    def chunk_types(self) -> set[str]:
        """WASM-specific chunk types."""
        return {
            "module",
            "function",
            "func",
            "memory",
            "table",
            "global",
            "export",
            "import",
            "type",
            "type_def",
            "data",
            "elem",
            "start",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".wat", ".wast"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"inline_func"},
                include_children=True,
                priority=5,
                metadata={"type": "inline_function"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"custom"},
                include_children=False,
                priority=4,
                metadata={"type": "custom_section"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("block_comment")


# Register the WASM configuration


class WASMPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for WebAssembly Text Format language chunking."""

    @property
    def language_name(self) -> str:
        return "wat"

    @property
    def supported_extensions(self) -> set[str]:
        return {".wat", ".wast"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "module",
            "function",
            "func",
            "memory",
            "table",
            "global",
            "export",
            "import",
            "type",
            "type_def",
            "data",
            "elem",
            "start",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a WASM node."""
        if node.type in {"function", "func"}:
            found_func = False
            for child in node.children:
                if child.type == "func" or (
                    child.type == "keyword"
                    and source[child.start_byte : child.end_byte] == b"func"
                ):
                    found_func = True
                elif found_func and child.type == "identifier":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    return name.lstrip("$")
        elif node.type == "export":
            for child in node.children:
                if child.type == "string":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    return name.strip('"')
        elif node.type == "import":
            strings = []
            for child in node.children:
                if child.type == "string":
                    s = source[child.start_byte : child.end_byte].decode("utf-8")
                    strings.append(s.strip('"'))
            if len(strings) >= 2:
                return f"{strings[0]}.{strings[1]}"
        elif node.type in {"global", "memory", "table"} or node.type in {
            "type",
            "type_def",
        }:
            for child in node.children:
                if child.type == "identifier":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    return name.lstrip("$")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to WebAssembly."""
        chunks = []
        module_name = None

        def extract_chunks(n: Node, in_module: bool = False):
            nonlocal module_name
            if n.type == "module":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                module_name = name
                chunk = {
                    "type": "module",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                chunks.append(chunk)
                for child in n.children:
                    extract_chunks(child, True)
                return
            if n.type in {"function", "func"} and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "function",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                params, results = self._extract_function_signature(n, source)
                if params is not None:
                    chunk["param_count"] = params
                if results is not None:
                    chunk["result_count"] = results
                if module_name:
                    chunk["module"] = module_name
                chunks.append(chunk)
            elif n.type == "memory" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "memory",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                limits = self._extract_memory_limits(n, source)
                if limits:
                    chunk["limits"] = limits
                chunks.append(chunk)
            elif n.type == "table" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "table",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "global" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "global",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                if self._is_mutable_global(n, source):
                    chunk["mutable"] = True
                chunks.append(chunk)
            elif n.type == "export" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "export",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                export_kind = self._get_export_kind(n, source)
                if export_kind:
                    chunk["export_kind"] = export_kind
                chunks.append(chunk)
            elif n.type == "import" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "import",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                import_kind = self._get_import_kind(n, source)
                if import_kind:
                    chunk["import_kind"] = import_kind
                chunks.append(chunk)
            elif n.type in {"type", "type_def"} and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "type_definition",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "data" and in_module:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "data_segment",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif not in_module:
                for child in n.children:
                    extract_chunks(child, in_module)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get WASM-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type == "inline_func":
            return True
        return node.type == "custom"

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format
        node_context_map = {
            "module": ("(module", ")"),
            "function": ("(func", ")"),
            "func": ("(func", ")"),
            "memory": ("(memory", ")"),
            "table": ("(table", ")"),
            "global": ("(global", ")"),
            "export": ('(export "', '")'),
            "import": ("(import", ")"),
            "type": ("(type", ")"),
            "type_def": ("(type", ")"),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        prefix, suffix = context_info
        name = self.get_node_name(node, source)
        if name:
            return f"{prefix} {name}{suffix}"
        return f"{prefix}{suffix}"

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process WASM nodes with special handling for modules and functions."""
        if node.type == "module":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                name = self.get_node_name(node, source)
                if name:
                    chunk.metadata = {"module_name": name}
                if self.should_include_chunk(chunk):
                    return chunk
        elif node.type in {"function", "func"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                params, results = self._extract_function_signature(
                    node,
                    source,
                )
                chunk.metadata = {
                    "param_count": params if params is not None else 0,
                    "result_count": results if results is not None else 0,
                }
                if self._is_exported_function(node, source):
                    chunk.metadata["exported"] = True
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "import":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                import_kind = self._get_import_kind(node, source)
                if import_kind:
                    chunk.metadata = {"import_kind": import_kind}
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "export":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                export_kind = self._get_export_kind(node, source)
                if export_kind:
                    chunk.metadata = {"export_kind": export_kind}
                return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)

    @staticmethod
    def _extract_function_signature(
        node: Node,
        _source: bytes,
    ) -> tuple[int | None, int | None]:
        """Extract parameter and result counts from function."""
        param_count = 0
        result_count = 0
        for child in node.children:
            if child.type == "param":
                param_count += 1
            elif child.type == "result":
                result_count += 1
        return param_count, result_count

    @staticmethod
    def _extract_memory_limits(node: Node, source: bytes) -> dict | None:
        """Extract memory limits (min/max pages)."""
        numbers = []
        for child in node.children:
            if child.type == "number":
                try:
                    num = int(source[child.start_byte : child.end_byte].decode("utf-8"))
                    numbers.append(num)
                except ValueError:
                    pass
        if numbers:
            limits = {"min": numbers[0]}
            if len(numbers) > 1:
                limits["max"] = numbers[1]
            return limits
        return None

    @staticmethod
    def _is_mutable_global(node: Node, source: bytes) -> bool:
        """Check if a global is mutable."""
        for child in node.children:
            if child.type == "mut" or (
                child.type == "keyword"
                and source[child.start_byte : child.end_byte] == b"mut"
            ):
                return True
        return False

    @staticmethod
    def _get_export_kind(node: Node, source: bytes) -> str | None:
        """Determine what kind of export this is."""
        for child in node.children:
            if child.type in {"func", "memory", "table", "global"}:
                return child.type
            if child.type == "keyword":
                keyword = source[child.start_byte : child.end_byte].decode("utf-8")
                if keyword in {"func", "memory", "table", "global"}:
                    return keyword
        return None

    def _get_import_kind(self, node: Node, source: bytes) -> str | None:
        """Determine what kind of import this is."""
        return self._get_export_kind(node, source)

    @staticmethod
    def _is_exported_function(_node: Node, _source: bytes) -> bool:
        """Check if this function is referenced by an export."""
        return False
