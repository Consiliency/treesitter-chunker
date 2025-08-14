"""
Support for NASM (Netwide Assembler) language.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class NASMConfig(LanguageConfig):
    """Language configuration for NASM."""

    @property
    def language_id(self) -> str:
        return "nasm"

    @property
    def chunk_types(self) -> set[str]:
        """NASM-specific chunk types."""
        return {
            "label",
            "section",
            "segment",
            "macro_definition",
            "struc_definition",
            "data_definition",
            "procedure",
            "global_directive",
            "extern_directive",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".asm", ".nasm", ".s", ".S"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"multi_macro_definition"},
                include_children=True,
                priority=6,
                metadata={"type": "multi_line_macro"},
            ),
        )
        self.add_chunk_rule(
            ChunkRule(
                node_types={"conditional_assembly"},
                include_children=True,
                priority=5,
                metadata={"type": "conditional"},
            ),
        )
        self.add_ignore_type("comment")
        self.add_ignore_type("line_comment")


# Register the NASM configuration


class NASMPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for NASM language chunking."""

    @property
    def language_name(self) -> str:
        return "nasm"

    @property
    def supported_extensions(self) -> set[str]:
        return {".asm", ".nasm", ".s", ".S"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "label",
            "section",
            "macro_definition",
            "struc_definition",
            "global_directive",
            "extern_directive",
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the name from a NASM node."""
        if node.type == "label":
            for child in node.children:
                if child.type == "word":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    return name.rstrip(":")
        elif (
            node.type == "assembl_directive_sections"
            or node.type == "preproc_multiline_macro"
            or (
                node.type == "struc_declaration"
                or node.type == "assembl_directive_symbols"
            )
        ):
            for child in node.children:
                if child.type == "word":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to NASM."""
        chunks = []
        current_section = None

        def extract_chunks(n: Node):
            nonlocal current_section
            if n.type == "label":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                chunk = {
                    "type": "label",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                if name and not name.startswith("."):
                    chunk["is_global"] = True
                else:
                    chunk["is_global"] = False
                if current_section:
                    chunk["section"] = current_section
                chunks.append(chunk)
            elif n.type == "assembl_directive_sections":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                name = self.get_node_name(n, source)
                current_section = name
                chunk = {
                    "type": "section",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": name,
                }
                chunks.append(chunk)
            elif n.type == "preproc_multiline_macro":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "macro",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "struc_declaration":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                chunk = {
                    "type": "struct",
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            elif n.type == "assembl_directive_symbols":
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                # Determine if this is global or extern based on content
                content_text = content.strip()
                if content_text.startswith("global"):
                    chunk_type = "global"
                elif content_text.startswith("extern"):
                    chunk_type = "extern"
                else:
                    chunk_type = "symbol"

                chunk = {
                    "type": chunk_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "name": self.get_node_name(n, source),
                }
                chunks.append(chunk)
            for child in n.children:
                extract_chunks(child)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get NASM-specific node types that form chunks."""
        return {
            "label",
            "assembl_directive_sections",
            "preproc_multiline_macro",
            "struc_declaration",
            "assembl_directive_symbols",
        }

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        return node.type in {
            "label",
            "assembl_directive_sections",
            "preproc_multiline_macro",
            "struc_declaration",
            "assembl_directive_symbols",
        }

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        # Handle special label case first
        if node.type == "label":
            return self._get_label_context(node, source)

        # Map node types to their context format
        node_context_map = {
            "assembl_directive_sections": ("section", "section"),
            "preproc_multiline_macro": ("%macro", "%macro"),
            "struc_declaration": ("struc", "struc"),
            "assembl_directive_symbols": ("", ""),
        }

        context_info = node_context_map.get(node.type)
        if not context_info:
            return None

        prefix, default = context_info
        name = self.get_node_name(node, source)

        # Special handling for assembl_directive_symbols
        if node.type == "assembl_directive_symbols":
            content = (
                source[node.start_byte : node.end_byte]
                .decode("utf-8", errors="replace")
                .strip()
            )
            if content.startswith("global"):
                return f"global {name}" if name else "global"
            if content.startswith("extern"):
                return f"extern {name}" if name else "extern"
            return f"{name}" if name else "symbol"

        return f"{prefix} {name}" if name else default

    def _get_label_context(self, node: Node, source: bytes) -> str:
        """Get context for label nodes."""
        name = self.get_node_name(node, source)
        if name and name.startswith("."):
            return f".{name}" if name else "local label"
        return f"{name}:" if name else "label"

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process NASM nodes with special handling for assembly constructs."""
        if node.type == "label":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                name = self.get_node_name(node, source)
                if name and name.startswith("."):
                    chunk.metadata = {"label_type": "local"}
                else:
                    chunk.metadata = {"label_type": "global"}
                next_instructions = self._get_following_instructions(node, source, 5)
                if self._is_procedure_prologue(next_instructions):
                    chunk.node_type = "procedure"
                    chunk.metadata["is_procedure"] = True
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "assembl_directive_sections":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                section_name = self.get_node_name(node, source)
                if section_name:
                    chunk.metadata = {"section_name": section_name}
                    if ".text" in section_name:
                        chunk.metadata["section_type"] = "code"
                    elif ".data" in section_name:
                        chunk.metadata["section_type"] = "data"
                    elif ".bss" in section_name:
                        chunk.metadata["section_type"] = "uninitialized_data"
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type == "preproc_multiline_macro":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                param_count = self._count_macro_parameters(node, source)
                chunk.metadata = {"parameter_count": param_count}
                return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)

    @staticmethod
    def _get_following_instructions(
        _node: Node,
        _source: bytes,
        _count: int,
    ) -> list[str]:
        """Get the next N instructions after a node."""
        instructions = []
        return instructions

    @staticmethod
    def _is_procedure_prologue(_instructions: list[str]) -> bool:
        """Check if instructions look like a procedure prologue."""
        return False

    @staticmethod
    def _count_macro_parameters(node: Node, source: bytes) -> int:
        """Count the number of parameters in a macro definition."""
        param_count = 0
        for child in node.children:
            if child.type == "preproc_multiline_macro_arg_spec":
                with contextlib.suppress(ValueError):
                    param_count = int(
                        source[child.start_byte : child.end_byte].decode("utf-8"),
                    )
                break
        return param_count
