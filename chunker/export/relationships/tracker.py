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
        # Index chunks
        self._chunk_index[source.chunk_id] = source
        self._chunk_index[target.chunk_id] = target

        # Create relationship
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
                if chunk.chunk_id in (r.source_chunk_id, r.target_chunk_id)
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
        # Build chunk index
        self._build_chunk_index(chunks)

        # Group chunks by file for efficient processing
        chunks_by_file = defaultdict(list)
        for chunk in chunks:
            chunks_by_file[chunk.file_path].append(chunk)

        # Analyze each file
        for file_chunks in chunks_by_file.values():
            if file_chunks:
                self._analyze_file_chunks(file_chunks)

        return self._relationships

    def clear(self) -> None:
        """Clear all tracked relationships."""
        self._relationships.clear()
        self._chunk_index.clear()
        self._parsers.clear()

    # Private helper methods

    def _build_chunk_index(self, chunks: list[CodeChunk]) -> None:
        """Build index of chunks for quick lookup."""
        for chunk in chunks:
            self._chunk_index[chunk.chunk_id] = chunk

    def _get_parser(self, language: str) -> Parser:
        """Get or create parser for language."""
        if language not in self._parsers:
            self._parsers[language] = get_parser(language)
        return self._parsers[language]

    def _analyze_file_chunks(self, chunks: list[CodeChunk]) -> None:
        """Analyze chunks from a single file."""
        if not chunks:
            return

        # Get file content and parser
        first_chunk = chunks[0]
        language = first_chunk.language

        try:
            parser = self._get_parser(language)
        except (FileNotFoundError, IndexError, KeyError):
            # Skip if language not supported
            return

        # Analyze based on language
        if language == "python":
            self._analyze_python_chunks(chunks, parser)
        elif language == "javascript":
            self._analyze_javascript_chunks(chunks, parser)
        elif language in ["c", "cpp"]:
            self._analyze_c_cpp_chunks(chunks, parser)
        elif language == "rust":
            self._analyze_rust_chunks(chunks, parser)

    def _analyze_python_chunks(self, chunks: list[CodeChunk], parser: Parser) -> None:
        """Analyze Python chunks for relationships."""
        for chunk in chunks:
            # Parse chunk content
            tree = parser.parse(chunk.content.encode())

            # Look for various relationship indicators
            self._find_python_imports(chunk, tree.root_node)
            self._find_python_calls(chunk, tree.root_node, chunks)
            self._find_python_inheritance(chunk, tree.root_node, chunks)

    def _analyze_javascript_chunks(
        self,
        chunks: list[CodeChunk],
        parser: Parser,
    ) -> None:
        """Analyze JavaScript chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())

            self._find_javascript_imports(chunk, tree.root_node)
            self._find_javascript_calls(chunk, tree.root_node, chunks)
            self._find_javascript_inheritance(chunk, tree.root_node, chunks)

    def _analyze_c_cpp_chunks(self, chunks: list[CodeChunk], parser: Parser) -> None:
        """Analyze C/C++ chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())

            self._find_c_includes(chunk, tree.root_node)
            self._find_c_calls(chunk, tree.root_node, chunks)

    def _analyze_rust_chunks(self, chunks: list[CodeChunk], parser: Parser) -> None:
        """Analyze Rust chunks for relationships."""
        for chunk in chunks:
            tree = parser.parse(chunk.content.encode())

            self._find_rust_uses(chunk, tree.root_node)
            self._find_rust_calls(chunk, tree.root_node, chunks)
            self._find_rust_impls(chunk, tree.root_node, chunks)

    # Python-specific analysis methods

    def _find_python_imports(self, chunk: CodeChunk, node: Node) -> None:
        """Find import statements in Python code."""
        if node.type in ["import_statement", "import_from_statement"]:
            # Extract imported names
            for child in node.children:
                if child.type in {"dotted_name", "identifier"}:
                    imported_name = chunk.content[child.start_byte : child.end_byte]
                    # Track as a dependency
                    self._add_dependency_relationship(chunk, imported_name)

        # Recurse
        for child in node.children:
            self._find_python_imports(chunk, child)

    def _find_python_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function/method calls in Python code."""
        if node.type == "call":
            # Get the function being called
            if node.children:
                func_node = node.children[0]
                if func_node.type == "identifier":
                    func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                    # Find matching chunk
                    target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                    if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                        self.track_relationship(
                            chunk,
                            target_chunk,
                            RelationshipType.CALLS,
                            {"function": func_name},
                        )

        # Recurse
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
            # Look for base classes in argument list
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier":
                            base_name = chunk.content[arg.start_byte : arg.end_byte]
                            # Find base class chunk
                            base_chunk = self._find_chunk_by_name(base_name, all_chunks)
                            if base_chunk and base_chunk.chunk_id != chunk.chunk_id:
                                self.track_relationship(
                                    chunk,
                                    base_chunk,
                                    RelationshipType.INHERITS,
                                    {"base_class": base_name},
                                )

        # Recurse
        for child in node.children:
            self._find_python_inheritance(chunk, child, all_chunks)

    # JavaScript-specific analysis methods

    def _find_javascript_imports(self, chunk: CodeChunk, node: Node) -> None:
        """Find import statements in JavaScript code."""
        if node.type in ["import_statement", "import_clause"]:
            # Extract imported module
            for child in node.children:
                if child.type == "string":
                    module_name = chunk.content[
                        child.start_byte + 1 : child.end_byte - 1
                    ]  # Remove quotes
                    self._add_dependency_relationship(chunk, module_name)

        # Recurse
        for child in node.children:
            self._find_javascript_imports(chunk, child)

    def _find_javascript_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in JavaScript code."""
        if node.type == "call_expression":
            # Get the function being called
            if node.children:
                func_node = node.children[0]
                if func_node.type == "identifier":
                    func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                    # Find matching chunk
                    target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                    if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                        self.track_relationship(
                            chunk,
                            target_chunk,
                            RelationshipType.CALLS,
                            {"function": func_name},
                        )

        # Recurse
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
            # Look for extends clause
            for child in node.children:
                if child.type == "class_heritage":
                    for heritage_child in child.children:
                        if heritage_child.type == "identifier":
                            base_name = chunk.content[
                                heritage_child.start_byte : heritage_child.end_byte
                            ]
                            # Find base class chunk
                            base_chunk = self._find_chunk_by_name(base_name, all_chunks)
                            if base_chunk and base_chunk.chunk_id != chunk.chunk_id:
                                self.track_relationship(
                                    chunk,
                                    base_chunk,
                                    RelationshipType.INHERITS,
                                    {"base_class": base_name},
                                )

        # Recurse
        for child in node.children:
            self._find_javascript_inheritance(chunk, child, all_chunks)

    # C/C++ specific analysis methods

    def _find_c_includes(self, chunk: CodeChunk, node: Node) -> None:
        """Find include statements in C/C++ code."""
        if node.type == "preproc_include":
            # Extract included file
            for child in node.children:
                if child.type in ["string_literal", "system_lib_string"]:
                    include_name = chunk.content[
                        child.start_byte : child.end_byte
                    ].strip('"<>')
                    self._add_dependency_relationship(chunk, include_name)

        # Recurse
        for child in node.children:
            self._find_c_includes(chunk, child)

    def _find_c_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in C/C++ code."""
        if node.type == "call_expression":
            # Get the function being called
            if node.children:
                func_node = node.children[0]
                if func_node.type == "identifier":
                    func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                    # Find matching chunk
                    target_chunk = self._find_chunk_by_name(func_name, all_chunks)
                    if target_chunk and target_chunk.chunk_id != chunk.chunk_id:
                        self.track_relationship(
                            chunk,
                            target_chunk,
                            RelationshipType.CALLS,
                            {"function": func_name},
                        )

        # Recurse
        for child in node.children:
            self._find_c_calls(chunk, child, all_chunks)

    # Rust-specific analysis methods

    def _find_rust_uses(self, chunk: CodeChunk, node: Node) -> None:
        """Find use statements in Rust code."""
        if node.type == "use_declaration":
            # Extract used module/item
            for child in node.children:
                if child.type in {"scoped_identifier", "identifier"}:
                    use_name = chunk.content[child.start_byte : child.end_byte]
                    self._add_dependency_relationship(chunk, use_name)

        # Recurse
        for child in node.children:
            self._find_rust_uses(chunk, child)

    def _find_rust_calls(
        self,
        chunk: CodeChunk,
        node: Node,
        all_chunks: list[CodeChunk],
    ) -> None:
        """Find function calls in Rust code."""
        if node.type == "call_expression":
            # Get the function being called
            if node.children:
                func_node = node.children[0]
                if func_node.type in {"identifier", "scoped_identifier"}:
                    func_name = chunk.content[func_node.start_byte : func_node.end_byte]
                    # Find matching chunk
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

        # Recurse
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
            # Look for trait implementation
            trait_name = None
            type_name = None

            for child in node.children:
                if child.type == "type_identifier" and trait_name is None:
                    trait_name = chunk.content[child.start_byte : child.end_byte]
                else:
                    type_name = chunk.content[child.start_byte : child.end_byte]

            if trait_name and type_name:
                # Find trait chunk
                trait_chunk = self._find_chunk_by_name(trait_name, all_chunks)
                if trait_chunk and trait_chunk.chunk_id != chunk.chunk_id:
                    self.track_relationship(
                        chunk,
                        trait_chunk,
                        RelationshipType.IMPLEMENTS,
                        {"trait": trait_name, "type": type_name},
                    )

        # Recurse
        for child in node.children:
            self._find_rust_impls(chunk, child, all_chunks)

    # Helper methods

    def _find_chunk_by_name(
        self,
        name: str,
        chunks: list[CodeChunk],
    ) -> CodeChunk | None:
        """Find a chunk by function/class name."""
        for chunk in chunks:
            # Simple heuristic: check if name appears at the beginning of a line
            # This could be improved with more sophisticated AST analysis
            lines = chunk.content.split("\n")
            for line in lines:
                # Look for function/class definitions
                if re.match(
                    rf"^\s*(def|class|function|fn|struct|impl)\s+{re.escape(name)}\b",
                    line,
                ):
                    return chunk
                # Also check for variable assignments (for lambdas, etc.)
                if re.match(rf"^\s*{re.escape(name)}\s*=", line):
                    return chunk
        return None

    def _add_dependency_relationship(self, chunk: CodeChunk, dependency: str) -> None:
        """Add a dependency relationship."""
        # For now, we just track the dependency name without linking to a specific chunk
        # This could be enhanced to resolve imports to actual chunks
        self.track_relationship(
            chunk,
            chunk,  # Self-reference for now
            RelationshipType.DEPENDS_ON,
            {"dependency": dependency},
        )
