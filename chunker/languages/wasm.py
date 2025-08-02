"""
Support for WebAssembly Text Format (WAT/WASM) language.
"""

from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class WASMConfig(LanguageConfig):
    """Language configuration for WebAssembly Text Format."""

    @property
    def language_id(self) -> str:
        return "wat"  # WebAssembly Text format

    @property
    def chunk_types(self) -> set[str]:
        """WASM-specific chunk types."""
        return {
            # Module level
            "module",
            # Functions
            "function",
            "func",
            # Memory
            "memory",
            # Tables
            "table",
            # Globals
            "global",
            # Exports
            "export",
            # Imports
            "import",
            # Types
            "type",
            "type_def",
            # Data segments
            "data",
            # Element segments
            "elem",
            # Start function
            "start",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".wat", ".wast"}

    def __init__(self):
        super().__init__()

        # Add rules for inline functions
        self.add_chunk_rule(
            ChunkRule(
                node_types={"inline_func"},
                include_children=True,
                priority=5,
                metadata={"type": "inline_function"},
            ),
        )

        # Add rules for custom sections
        self.add_chunk_rule(
            ChunkRule(
                node_types={"custom"},
                include_children=False,
                priority=4,
                metadata={"type": "custom_section"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("comment")
        self.add_ignore_type("block_comment")


# Register the WASM configuration

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


# Plugin implementation for backward compatibility
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

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the name from a WASM node."""
        # For functions, look for identifier after func keyword
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
                    # Remove $ prefix if present
                    return name.lstrip("$")

        # For exports, get the exported name
        elif node.type == "export":
            for child in node.children:
                if child.type == "string":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    # Remove quotes
                    return name.strip('"')

        # For imports, get module and name
        elif node.type == "import":
            strings = []
            for child in node.children:
                if child.type == "string":
                    s = source[child.start_byte : child.end_byte].decode("utf-8")
                    strings.append(s.strip('"'))
            if len(strings) >= 2:
                return f"{strings[0]}.{strings[1]}"

        # For globals, memory, tables
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

            # Module declarations
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

                # Process module contents
                for child in n.children:
                    extract_chunks(child, True)
                return

            # Functions
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

                # Extract function signature info
                params, results = self._extract_function_signature(n, source)
                if params is not None:
                    chunk["param_count"] = params
                if results is not None:
                    chunk["result_count"] = results

                if module_name:
                    chunk["module"] = module_name

                chunks.append(chunk)

            # Memory declarations
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

                # Extract memory limits
                limits = self._extract_memory_limits(n, source)
                if limits:
                    chunk["limits"] = limits

                chunks.append(chunk)

            # Table declarations
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

            # Global declarations
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

                # Check if mutable
                if self._is_mutable_global(n, source):
                    chunk["mutable"] = True

                chunks.append(chunk)

            # Exports
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

                # Get export kind
                export_kind = self._get_export_kind(n, source)
                if export_kind:
                    chunk["export_kind"] = export_kind

                chunks.append(chunk)

            # Imports
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

                # Get import kind
                import_kind = self._get_import_kind(n, source)
                if import_kind:
                    chunk["import_kind"] = import_kind

                chunks.append(chunk)

            # Type definitions
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

            # Data segments
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

            # Continue traversal for non-module nodes
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
        # All default chunk types should be chunked
        if node.type in self.default_chunk_types:
            return True

        # Inline functions
        if node.type == "inline_func":
            return True

        # Custom sections
        return node.type == "custom"

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)

        if node.type == "module":
            return f"(module {name})" if name else "(module)"

        if node.type in {"function", "func"}:
            return f"(func {name})" if name else "(func)"

        if node.type == "memory":
            return f"(memory {name})" if name else "(memory)"

        if node.type == "table":
            return f"(table {name})" if name else "(table)"

        if node.type == "global":
            return f"(global {name})" if name else "(global)"

        if node.type == "export":
            return f'(export "{name}")' if name else "(export)"

        if node.type == "import":
            return f"(import {name})" if name else "(import)"

        if node.type in {"type", "type_def"}:
            return f"(type {name})" if name else "(type)"

        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process WASM nodes with special handling for modules and functions."""
        # Handle module nodes
        if node.type == "module":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                name = self.get_node_name(node, source)
                if name:
                    chunk.metadata = {"module_name": name}
                # Don't include the entire module as a chunk if it's too large
                if self.should_include_chunk(chunk):
                    return chunk

        # Handle functions with signature extraction
        elif node.type in {"function", "func"}:
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                # Extract function metadata
                params, results = self._extract_function_signature(node, source)
                chunk.metadata = {
                    "param_count": params if params is not None else 0,
                    "result_count": results if results is not None else 0,
                }

                # Check if it's an exported function
                if self._is_exported_function(node, source):
                    chunk.metadata["exported"] = True

                return chunk if self.should_include_chunk(chunk) else None

        # Handle imports with type info
        elif node.type == "import":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                import_kind = self._get_import_kind(node, source)
                if import_kind:
                    chunk.metadata = {"import_kind": import_kind}
                return chunk if self.should_include_chunk(chunk) else None

        # Handle exports with kind info
        elif node.type == "export":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                export_kind = self._get_export_kind(node, source)
                if export_kind:
                    chunk.metadata = {"export_kind": export_kind}
                return chunk if self.should_include_chunk(chunk) else None

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

    def _extract_function_signature(
        self,
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

        return (param_count, result_count)

    def _extract_memory_limits(self, node: Node, source: bytes) -> dict | None:
        """Extract memory limits (min/max pages)."""
        # Look for numeric limits in memory declaration
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

    def _is_mutable_global(self, node: Node, source: bytes) -> bool:
        """Check if a global is mutable."""
        for child in node.children:
            if child.type == "mut" or (
                child.type == "keyword"
                and source[child.start_byte : child.end_byte] == b"mut"
            ):
                return True
        return False

    def _get_export_kind(self, node: Node, source: bytes) -> str | None:
        """Determine what kind of export this is."""
        # Look for func, memory, table, global keywords
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
        # Similar to export kind
        return self._get_export_kind(node, source)

    def _is_exported_function(self, _node: Node, _source: bytes) -> bool:
        """Check if this function is referenced by an export."""
        # This would require more complex analysis of the module
        # For now, return False
        return False
