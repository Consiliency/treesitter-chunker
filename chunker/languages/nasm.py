"""
Support for NASM (Netwide Assembler) language.
"""
from __future__ import annotations

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class NASMConfig(LanguageConfig):
    """Language configuration for NASM."""

    @property
    def language_id(self) -> str:
        return "nasm"

    @property
    def chunk_types(self) -> set[str]:
        """NASM-specific chunk types."""
        return {"label", "section", "segment", "macro_definition",
            "struc_definition", "data_definition", "procedure",
            "global_directive", "extern_directive"}

    @property
    def file_extensions(self) -> set[str]:
        return {".asm", ".nasm", ".s", ".S"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(ChunkRule(node_types={"multi_macro_definition"},
            include_children=True, priority=6, metadata={"type":
            "multi_line_macro"}))
        self.add_chunk_rule(ChunkRule(node_types={"conditional_assembly"},
            include_children=True, priority=5, metadata={"type":
            "conditional"}))
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
        return {"label", "section", "segment", "macro_definition",
            "struc_definition", "data_definition", "global_directive",
            "extern_directive"}

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> (str | None):
        """Extract the name from a NASM node."""
        if node.type == "label":
            for child in node.children:
                if child.type == "identifier":
                    name = source[child.start_byte:child.end_byte].decode(
                        "utf-8")
                    return name.rstrip(":")
        elif node.type in {"section", "segment"}:
            for child in node.children:
                if child.type in {"identifier", "section_name"}:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type == "macro_definition":
            for i, child in enumerate(node.children):
                if child.type == "identifier" and i > 0:
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        elif node.type == "struc_definition" or node.type in {
            "global_directive", "extern_directive"}:
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte:child.end_byte].decode(
                        "utf-8")
        return None

    @staticmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to NASM."""
        chunks = []
        current_section = None

        def extract_chunks(n: Node):
            nonlocal current_section
            if n.type == "label":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                name = self.get_node_name(n, source)
                chunk = {"type": "label", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": name}
                if name and not name.startswith("."):
                    chunk["is_global"] = True
                else:
                    chunk["is_global"] = False
                if current_section:
                    chunk["section"] = current_section
                chunks.append(chunk)
            elif n.type in {"section", "segment"}:
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                name = self.get_node_name(n, source)
                current_section = name
                chunk = {"type": "section", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": name}
                chunks.append(chunk)
            elif n.type == "macro_definition":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": "macro", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                chunks.append(chunk)
            elif n.type == "struc_definition":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": "struct", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                chunks.append(chunk)
            elif n.type == "global_directive":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": "global", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                chunks.append(chunk)
            elif n.type == "extern_directive":
                content = source[n.start_byte:n.end_byte].decode("utf-8",
                    errors="replace")
                chunk = {"type": "extern", "start_line": n.start_point[0] +
                    1, "end_line": n.end_point[0] + 1, "content": content,
                    "name": self.get_node_name(n, source)}
                chunks.append(chunk)
            for child in n.children:
                extract_chunks(child)
        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get NASM-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        if node.type in self.default_chunk_types:
            return True
        if node.type == "multi_macro_definition":
            return True
        if node.type == "conditional_assembly":
            return len(node.children) > 3
        if node.type == "data_definition":
            return node.end_point[0] - node.start_point[0] > 2
        return False

    def get_node_context(self, node: Node, source: bytes) -> (str | None):
        """Extract meaningful context for a node."""
        name = self.get_node_name(node, source)
        if node.type == "label":
            if name and name.startswith("."):
                return f".{name}" if name else "local label"
            return f"{name}:" if name else "label"
        if node.type in {"section", "segment"}:
            return f"section {name}" if name else "section"
        if node.type == "macro_definition":
            return f"%macro {name}" if name else "%macro"
        if node.type == "struc_definition":
            return f"struc {name}" if name else "struc"
        if node.type == "global_directive":
            return f"global {name}" if name else "global"
        if node.type == "extern_directive":
            return f"extern {name}" if name else "extern"
        return None

    def process_node(self, node: Node, source: bytes, file_path: str,
        parent_context: (str | None) = None):
        """Process NASM nodes with special handling for assembly constructs."""
        if node.type == "label":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                name = self.get_node_name(node, source)
                if name and name.startswith("."):
                    chunk.metadata = {"label_type": "local"}
                else:
                    chunk.metadata = {"label_type": "global"}
                next_instructions = self._get_following_instructions(node,
                    source, 5)
                if self._is_procedure_prologue(next_instructions):
                    chunk.node_type = "procedure"
                    chunk.metadata["is_procedure"] = True
                return chunk if self.should_include_chunk(chunk) else None
        elif node.type in {"section", "segment"}:
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
        elif node.type == "macro_definition":
            chunk = self.create_chunk(node, source, file_path, parent_context)
            if chunk:
                param_count = self._count_macro_parameters(node, source)
                chunk.metadata = {"parameter_count": param_count}
                return chunk if self.should_include_chunk(chunk) else None
        return super().process_node(node, source, file_path, parent_context)

    @staticmethod
    def _get_following_instructions(_node: Node, _source: bytes, _count: int,
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
        for i, child in enumerate(node.children):
            if child.type == "number" and i > 1:
                with contextlib.suppress(ValueError):
                    param_count = int(source[child.start_byte:child.
                        end_byte].decode("utf-8"))
                break
        return param_count
