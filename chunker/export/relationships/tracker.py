"""Track and infer relationships between code chunks using Tree-sitter AST."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from chunker.interfaces.export import (
    ChunkRelationship,
    RelationshipTracker,
    RelationshipType,
)
from chunker.parser import get_parser

if TYPE_CHECKING:
    from tree_sitter import Node, Parser

    from chunker.types import CodeChunk


class ASTRelationshipTracker(RelationshipTracker):
    """Track relationships between chunks using AST analysis."""

    def __init__(self):
        self._relationships: list[ChunkRelationship] = []
        self._chunk_index: dict[str, CodeChunk] = {}
        self._parsers: dict[str, Parser] = {}

    def track_relationship(
        self,
        source: CodeChunk,
        target: CodeChunk,
        relationship_type: RelationshipType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track a relationship between chunks.

        Args:
            source: Source chunk
            target: Target chunk
            relationship_type: Type of relationship
            metadata: Additional metadata
        """
        self._chunk_index[source.chunk_id] = source
        self._chunk_index[target.chunk_id] = target
        relationship = ChunkRelationship(
            source_chunk_id=source.chunk_id,
            target_chunk_id=target.chunk_id,
            relationship_type=relationship_type,
            metadata=metadata or {},
        )
        self._relationships.append(relationship)

    def get_relationships(
        self,
        chunk: CodeChunk | None = None,
        relationship_type: RelationshipType | None = None,
    ) -> list[ChunkRelationship]:
        """Get tracked relationships.

        Args:
            chunk: Filter by specific chunk (None for all)
            relationship_type: Filter by type (None for all)

        Returns:
            List of relationships
        """
        results = self._relationships
        if chunk:
            results = [
                r
                for r in results
                if chunk.chunk_id in {r.source_chunk_id, r.target_chunk_id}
            ]
        if relationship_type:
            results = [r for r in results if r.relationship_type == relationship_type]
        return results

    def infer_relationships(self, chunks: list[CodeChunk]) -> list[ChunkRelationship]:
        """Infer relationships from chunk data using AST analysis.

        Args:
            chunks: List of chunks to analyze

        Returns:
            List of inferred relationships
        """
        self._build_chunk_index(chunks)
        chunks_by_file = defaultdict(list)
        for chunk in chunks:
            chunks_by_file[chunk.file_path].append(chunk)
        for file_chunks in chunks_by_file.values():
            if file_chunks:
                self._analyze_file_chunks(file_chunks, chunks)
        return self._relationships

    def clear(self) -> None:
        """Clear all tracked relationships."""
        self._relationships.clear()
        self._chunk_index.clear()
        self._parsers.clear()

    def _build_chunk_index(self, chunks: list[CodeChunk]) -> None:
        """Build index of chunks for quick lookup."""
        for chunk in chunks:
            self._chunk_index[chunk.chunk_id] = chunk

    def _get_parser(self, language: str) -> Parser:
        """Get or create parser for language."""
        if language not in self._parsers:
            self._parsers[language] = get_parser(language)
        return self._parsers[language]

    def _analyze_file_chunks(
        self,
        file_chunks: list[CodeChunk],
        all_chunks: list[CodeChunk],
    ) -> None:
        """Analyze chunks from a single file.

        Args:
            file_chunks: Chunks from the current file being analyzed
            all_chunks: All chunks from all files for cross-file lookups
        """
        if not file_chunks:
            return
        first_chunk = file_chunks[0]
        language = first_chunk.language
        try:
            parser = self._get_parser(language)
        except (FileNotFoundError, IndexError, KeyError):
            return
        if language == "python":
            self._analyze_python_chunks(file_chunks, parser, all_chunks)
        elif language == "javascript":
            self._analyze_javascript_chunks(file_chunks, parser, all_chunks)
        elif language in {"c", "cpp"}:
            self._analyze_c_cpp_chunks(file_chunks, parser, all_chunks)
        elif language == "rust":
            self._analyze_rust_chunks(file_chunks, parser, all_chunks)

    def _analyze_python_chunks(
        self,
        chunks: list[CodeChunk],
        parser: Parser,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Analyze Python chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())
            self._find_python_imports(chunk, tree.root_node)
            self._find_python_calls(chunk, tree.root_node, all_chunks)
            self._find_python_inheritance(chunk, tree.root_node, all_chunks)

    def _analyze_javascript_chunks(
        self,
        chunks: list[CodeChunk],
        parser: Parser,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Analyze JavaScript chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())
            self._find_javascript_imports(chunk, tree.root_node)
            self._find_javascript_calls(chunk, tree.root_node, all_chunks)
            self._find_javascript_inheritance(chunk, tree.root_node, all_chunks)

    def _analyze_c_cpp_chunks(
        self,
        chunks: list[CodeChunk],
        parser: Parser,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Analyze C/C++ chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())
            self._find_c_includes(chunk, tree.root_node)
            self._find_c_calls(chunk, tree.root_node, all_chunks)

    def _analyze_rust_chunks(
        self,
        chunks: list[CodeChunk],
        parser: Parser,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Analyze Rust chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())
            self._find_rust_uses(chunk, tree.root_node)
            self._find_rust_calls(chunk, tree.root_node, all_chunks)
            self._find_rust_impls(chunk, tree.root_node, all_chunks)

    def _find_python_imports(self, chunk: CodeChunk, node: Node) -> None:
        """Find import statements in Python code."""
        if node.type in {"import_statement", "import_from_statement"}:
            for child in node.children:
                if child.type in {"dotted_name", "identifier"}:
                    imported_name = chunk.content[child.start_byte : child.end_byte]
                    self._add_dependency_relationship(chunk, imported_name)
        for child in node.children:
            self._find_python_imports(chunk, child)

    def _find_python_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function/method calls in Python code."""
        if node.type == "call" and node.children:
            func_node = node.children[0]
            if func_node.type == "identifier":
                func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        target_chunk,
                        RelationshipType.CALLS,
                        {"function": func_name},
                    )
        for child in node.children:
            self._find_python_calls(chunk, child, all_chunks)

    def _find_python_inheritance(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find class inheritance in Python code."""
        if node.type == "class_definition":
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier":
                            base_name = chunk.content[arg.start_byte : arg.end_byte]
                            base_chunk = self._find_chunk_by_name(base_name, all_chunks)
                            if base_chunk and base_chunk.chunk_id != chunk.chunk_id:
                                self.track_relationship(
                                    chunk,
                                    base_chunk,
                                    RelationshipType.INHERITS,
                                    {"base_class": base_name},
                                )
        for child in node.children:
            self._find_python_inheritance(chunk, child, all_chunks)

    def _find_javascript_imports(self, chunk: CodeChunk, node: Node) -> None:
        """Find import statements in JavaScript code."""
        if node.type in {"import_statement", "import_clause"}:
            for child in node.children:
                if child.type == "string":
                    module_name = chunk.content[
                        child.start_byte + 1 : child.end_byte - 1
                    ]
                    self._add_dependency_relationship(chunk, module_name)
        for child in node.children:
            self._find_javascript_imports(chunk, child)

    def _find_javascript_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in JavaScript code."""
        if node.type == "call_expression" and node.children:
            callee = node.children[0]
            # Extract a sensible function name from identifiers or member expressions
            func_name: str | None = None
            if callee.type == "identifier":
                func_name = chunk.content[callee.start_byte : callee.end_byte]
            elif callee.type in {"member_expression", "subscript_expression"}:
                # Walk right-most property/identifier
                func_name = self._extract_js_member_tail(chunk, callee)
            if func_name:
                target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        target_chunk,
                        RelationshipType.CALLS,
                        {"function": func_name},
                    )
        for child in node.children:
            self._find_javascript_calls(chunk, child, all_chunks)

    def _find_javascript_inheritance(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find class inheritance in JavaScript code."""
        if node.type == "class_declaration":
            for child in node.children:
                if child.type == "class_heritage":
                    # class_heritage may contain identifier or member_expression
                    base_name = None
                    for heritage_child in child.children:
                        if heritage_child.type == "identifier":
                            base_name = chunk.content[
                                heritage_child.start_byte : heritage_child.end_byte
                            ]
                            break
                        if heritage_child.type in {
                            "member_expression",
                            "scoped_identifier",
                        }:
                            base_name = self._extract_js_member_tail(
                                chunk,
                                heritage_child,
                            )
                            break
                    if base_name:
                        base_chunk = self._find_chunk_by_name(base_name, all_chunks)
                        if base_chunk and base_chunk.chunk_id != chunk.chunk_id:
                            self.track_relationship(
                                chunk,
                                base_chunk,
                                RelationshipType.INHERITS,
                                {"base_class": base_name},
                            )
        for child in node.children:
            self._find_javascript_inheritance(chunk, child, all_chunks)

    def _extract_js_member_tail(self, chunk: CodeChunk, node: Node) -> str | None:
        """Extract the right-most identifier name from a JS member/subscript expression."""
        # Attempt to find the last identifier-like child
        tail: str | None = None
        stack = [node]
        while stack:
            current = stack.pop()
            for child in getattr(current, "children", [])[::-1]:
                if child.type in {"identifier", "property_identifier"}:
                    return chunk.content[child.start_byte : child.end_byte]
                stack.append(child)
        return tail

    def _find_c_includes(self, chunk: CodeChunk, node: Node) -> None:
        """Find include statements in C/C++ code."""
        if node.type == "preproc_include":
            for child in node.children:
                if child.type in {"string_literal", "system_lib_string"}:
                    include_name = chunk.content[
                        child.start_byte : child.end_byte
                    ].strip('"<>')
                    self._add_dependency_relationship(chunk, include_name)
        for child in node.children:
            self._find_c_includes(chunk, child)

    def _find_c_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in C/C++ code."""
        if node.type == "call_expression" and node.children:
            func_node = node.children[0]
            if func_node.type == "identifier":
                func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        target_chunk,
                        RelationshipType.CALLS,
                        {"function": func_name},
                    )
            # Support member expressions obj.method()
            elif func_node.type in {"member_expression", "call_expression"}:
                name = self._extract_member_name(func_node, chunk.content)
                if name:
                    target_chunk = self._find_chunk_by_name(name, all_chunks)
                    if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                        self.track_relationship(
                            chunk,
                            target_chunk,
                            RelationshipType.CALLS,
                            {"function": name},
                        )
        for child in node.children:
            self._find_c_calls(chunk, child, all_chunks)

    def _find_rust_uses(self, chunk: CodeChunk, node: Node) -> None:
        """Find use statements in Rust code."""
        if node.type == "use_declaration":
            for child in node.children:
                if child.type in {"scoped_identifier", "identifier"}:
                    use_name = chunk.content[child.start_byte : child.end_byte]
                    self._add_dependency_relationship(chunk, use_name)
        for child in node.children:
            self._find_rust_uses(chunk, child)

    def _find_rust_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in Rust code."""
        if node.type == "call_expression" and node.children:
            func_node = node.children[0]
            if func_node.type in {"identifier", "scoped_identifier"}:
                func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                target_chunk = self._find_chunk_by_name(
                    func_name.split("::")[-1],
                    all_chunks,
                )
                if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        target_chunk,
                        RelationshipType.CALLS,
                        {"function": func_name},
                    )
        for child in node.children:
            self._find_rust_calls(chunk, child, all_chunks)

    def _find_rust_impls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find impl blocks in Rust code."""
        if node.type == "impl_item":
            trait_name = None
            type_name = None
            for child in node.children:
                if child.type == "type_identifier" and trait_name is None:
                    trait_name = chunk.content[child.start_byte : child.end_byte]
                else:
                    type_name = chunk.content[child.start_byte : child.end_byte]
            if trait_name and type_name:
                trait_chunk = self._find_chunk_by_name(trait_name, all_chunks)
                if trait_chunk and trait_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        trait_chunk,
                        RelationshipType.IMPLEMENTS,
                        {"trait": trait_name, "type": type_name},
                    )
        for child in node.children:
            self._find_rust_impls(chunk, child, all_chunks)

    @staticmethod
    def _find_chunk_by_name(name: str, chunks: list[CodeChunk]) -> CodeChunk | None:
        """Find a chunk by function/class name.

        Attempts structured metadata first (signature/exports), then falls back to
        textual heuristics. Supports dotted names by comparing the tail.
        """
        simple_name = name.rsplit(".", maxsplit=1)[-1]
        for chunk in chunks:
            try:
                sig = (
                    chunk.metadata.get("signature")
                    if hasattr(chunk, "metadata")
                    else None
                )
                if isinstance(sig, dict):
                    sig_name = sig.get("name")
                    if isinstance(sig_name, str) and sig_name == simple_name:
                        return chunk
                exports = (
                    chunk.metadata.get("exports")
                    if hasattr(chunk, "metadata")
                    else None
                )
                if isinstance(exports, (list, tuple)) and simple_name in exports:
                    return chunk
            except Exception:
                pass
            lines = chunk.content.split("\n")
            for line in lines:
                if re.match(
                    f"^\\s*(def|class|function|fn|struct|impl)\\s+{re.escape(simple_name)}\\b",
                    line,
                ):
                    return chunk
                # JS/TS method shorthand or assignment
                if re.match(f"^\\s*{re.escape(simple_name)}\\s*\\(", line):
                    return chunk
                if re.match(f"^\\s*{re.escape(simple_name)}\\s*=", line):
                    return chunk
        return None

    def _add_dependency_relationship(
        self,
        chunk: CodeChunk,
        dependency: str,
    ) -> None:
        """Add a dependency relationship."""
        self.track_relationship(
            chunk,
            chunk,
            RelationshipType.DEPENDS_ON,
            {"dependency": dependency},
        )
