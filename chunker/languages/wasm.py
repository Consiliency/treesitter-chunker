"""
Support for WebAssembly Text Format (WAT/WASM) language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode_bytes

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
            "module_field_func",
            "module_field_memory",
            "module_field_table",
            "module_field_global",
            "module_field_import",
            "module_field_export",
            "module_field_type",
            "module_field_data",
            "module_field_elem",
            "module_field_start",
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
            "module_field_func",
            "module_field_memory",
            "module_field_table",
            "module_field_global",
            "module_field_import",
            "module_field_export",
            "module_field_type",
            "module_field_data",
            "module_field_elem",
            "module_field_start",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a WASM node."""
        if node.type == "module":
            # Look for an identifier child in the module node
            for child in node.children:
                if child.type == "identifier":
                    name = safe_decode_bytes(source[child.start_byte : child.end_byte])
                    return name.lstrip("$")
        elif node.type == "module_field_func":
            # Look for the identifier child in function
            for child in node.children:
                if child.type == "identifier":
                    name = safe_decode_bytes(source[child.start_byte : child.end_byte])
                    return name.lstrip("$")
        elif node.type in {
            "module_field_memory",
            "module_field_table",
            "module_field_global",
            "module_field_type",
        }:
            # Look for identifier child in these module fields
            for child in node.children:
                if child.type == "identifier":
                    name = safe_decode_bytes(source[child.start_byte : child.end_byte])
                    return name.lstrip("$")
        elif node.type == "module_field_export":
            # Look for the name field which contains a string
            for child in node.children:
                if child.type == "name":
                    for name_child in child.children:
                        if name_child.type == "string":
                            name = safe_decode_bytes(
                                source[name_child.start_byte : name_child.end_byte],
                            )
                            return name.strip('"')
        elif node.type == "module_field_import":
            # Look for name fields (module and name)
            names = []
            for child in node.children:
                if child.type == "name":
                    for name_child in child.children:
                        if name_child.type == "string":
                            name = safe_decode_bytes(
                                source[name_child.start_byte : name_child.end_byte],
                            )
                            names.append(name.strip('"'))
            if len(names) >= 2:
                return f"{names[0]}.{names[1]}"
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
                # Process child module fields directly
                for child in n.children:
                    if child.type == "module_field":
                        for field_child in child.children:
                            extract_chunks(field_child, True)
                return
            if n.type == "module_field_func" and in_module:
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
            elif n.type == "module_field_memory" and in_module:
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

                # Check for inline export
                inline_export = self._extract_inline_export(n, source)
                if inline_export:
                    export_chunk = {
                        "type": "export",
                        "start_line": n.start_point[0] + 1,
                        "end_line": n.end_point[0] + 1,
                        "content": content,
                        "name": inline_export,
                        "export_kind": "memory",
                    }
                    chunks.append(export_chunk)
            elif n.type == "module_field_table" and in_module:
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
            elif n.type == "module_field_global" and in_module:
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
            elif n.type == "module_field_export" and in_module:
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
            elif n.type == "module_field_import" and in_module:
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
            elif n.type == "module_field_type" and in_module:
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
            elif n.type == "module_field_data" and in_module:
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
        return node.type in self.default_chunk_types

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Map node types to their context format
        node_context_map = {
            "module": ("(module", ")"),
            "module_field_func": ("(func", ")"),
            "module_field_memory": ("(memory", ")"),
            "module_field_table": ("(table", ")"),
            "module_field_global": ("(global", ")"),
            "module_field_export": ('(export "', '")'),
            "module_field_import": ("(import", ")"),
            "module_field_type": ("(type", ")"),
            "module_field_data": ("(data", ")"),
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
        elif node.type == "module_field_func":
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
        elif node.type == "module_field_import":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                import_kind = self._get_import_kind(node, source)
                if import_kind:
                    chunk.metadata = {"import_kind": import_kind}
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "module_field_export":
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

        # Count direct children of func_type_params and func_type_results
        for child in node.children:
            if child.type == "func_type_params":
                param_count += 1
            elif child.type == "func_type_results":
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
            if child.type == "global_type":
                for global_type_child in child.children:
                    if global_type_child.type == "global_type_mut":
                        return True
        return False

    @staticmethod
    def _get_export_kind(node: Node, source: bytes) -> str | None:
        """Determine what kind of export this is."""
        for child in node.children:
            if child.type == "export_desc":
                for desc_child in child.children:
                    if desc_child.type == "export_desc_func":
                        return "func"
                    if desc_child.type == "export_desc_memory":
                        return "memory"
                    if desc_child.type == "export_desc_table":
                        return "table"
                    if desc_child.type == "export_desc_global":
                        return "global"
        return None

    def _get_import_kind(self, node: Node, source: bytes) -> str | None:
        """Determine what kind of import this is."""
        for child in node.children:
            if child.type == "import_desc":
                for desc_child in child.children:
                    if desc_child.type == "import_desc_func_type":
                        return "func"
                    if desc_child.type == "import_desc_memory_type":
                        return "memory"
                    if desc_child.type == "import_desc_table_type":
                        return "table"
                    if desc_child.type == "import_desc_global_type":
                        return "global"
                    if desc_child.type == "import_desc_type_use":
                        return "func"  # type_use typically refers to function types
        return None

    @staticmethod
    def _extract_inline_export(node: Node, source: bytes) -> str | None:
        """Extract inline export name if present."""
        for child in node.children:
            if child.type == "export":
                for export_child in child.children:
                    if export_child.type == "name":
                        for name_child in export_child.children:
                            if name_child.type == "string":
                                name = source[
                                    name_child.start_byte : name_child.end_byte
                                ].decode("utf-8")
                                return name.strip('"')
        return None

    @staticmethod
    def _is_exported_function(_node: Node, _source: bytes) -> bool:
        """Check if this function is referenced by an export."""
        return False
