"""Semantic chunking strategy using AST semantics for intelligent boundaries."""
from typing import Any

from tree_sitter import Node

from chunker.analysis import ComplexityAnalyzer, CouplingAnalyzer, SemanticAnalyzer
from chunker.interfaces.base import ChunkingStrategy
from chunker.types import CodeChunk


class SemanticChunker(ChunkingStrategy):
    """Chunks code based on semantic boundaries and relationships.

    Uses AST semantic analysis to create chunks that:
    - Maintain semantic cohesion
    - Respect logical boundaries
    - Group related functionality
    - Consider coupling and dependencies
    """

    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.coupling_analyzer = CouplingAnalyzer()
        self.config = {"min_chunk_size": 10, "max_chunk_size": 200,
            "complexity_threshold": 15.0, "coupling_threshold": 10.0,
            "cohesion_threshold": 0.7, "merge_related": True,
            "split_complex": True}
        self.semantic_boundaries = {"module", "program", "translation_unit",
            "class_definition", "class_declaration",
            "interface_declaration", "trait_definition",
            "function_definition", "function_declaration",
            "method_definition", "method_declaration",
            "constructor_definition", "destructor_definition",
            "namespace_definition", "impl_item", "export_statement",
            "import_statement", "test_definition", "test_suite",
            "describe_block"}
        self.cohesive_groups = {"property_group": ["property_declaration",
            "field_declaration"], "method_group": ["method_definition",
            "method_declaration"], "import_group": ["import_statement",
            "import_from_statement"], "type_group": ["type_alias",
            "type_definition", "interface_declaration"]}

    @staticmethod
    def can_handle(_file_path: str, language: str) -> bool:
        """Semantic chunking can handle any language with proper AST support."""
        supported_languages = {"python", "javascript", "typescript", "java",
            "c", "cpp", "rust", "go", "ruby", "php"}
        return language in supported_languages

    def chunk(self, ast: Node, source: bytes, file_path: str, language: str,
        ) -> list[CodeChunk]:
        """Create semantically coherent chunks from the AST."""
        chunks = []
        semantic_nodes = self._identify_semantic_nodes(ast, source)
        for node, metadata in semantic_nodes:
            chunk = self._create_semantic_chunk(node, source, file_path,
                language, metadata)
            if chunk:
                chunks.append(chunk)
        if self.config["merge_related"]:
            chunks = self._merge_related_chunks(chunks, source)
        if self.config["split_complex"]:
            chunks = self._split_complex_chunks(chunks, ast, source,
                file_path, language)
        chunks = self._optimize_chunks(chunks)
        return chunks

    def configure(self, config: dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)

    def _identify_semantic_nodes(ast: Node, source: bytes) -> list[tuple[
        Node, dict[str, Any]]]:
        """Identify nodes that form semantic boundaries."""
        semantic_nodes = []

        def traverse(node: Node, depth: int = 0, parent_semantic: bool = False):
            semantic_info = self.semantic_analyzer.analyze_semantics(node,
                source)
            complexity_info = self.complexity_analyzer.calculate_complexity(
                node, source)
            is_boundary = (node.type in self.semantic_boundaries or
                complexity_info["score"] > self.config[
                "complexity_threshold"] or semantic_info["cohesion_score"] >
                self.config["cohesion_threshold"])
            if is_boundary and not parent_semantic:
                metadata = {"semantic": semantic_info, "complexity":
                    complexity_info, "depth": depth}
                semantic_nodes.append((node, metadata))
                parent_semantic = True
            for child in node.children:
                traverse(child, depth + 1, parent_semantic)
        traverse(ast)
        return semantic_nodes

    def _create_semantic_chunk(self, node: Node, source: bytes, file_path:
        str, language: str, metadata: dict[str, Any]) -> CodeChunk:
        """Create a chunk from a semantic node."""
        line_count = node.end_point[0] - node.start_point[0] + 1
        if line_count < self.config["min_chunk_size"]:
            return None
        content = source[node.start_byte:node.end_byte].decode("utf-8",
            errors="replace")
        parent_context = self._determine_parent_context(node, source)
        chunk = CodeChunk(language=language, file_path=file_path, node_type=node.type, start_line=node.start_point[0] + 1, end_line=node.
            end_point[0] + 1, byte_start=node.start_byte, byte_end=node.
            end_byte, parent_context=parent_context, content=content)
        chunk.metadata = metadata
        coupling_info = self.coupling_analyzer.analyze_coupling(node, source)
        chunk.dependencies = coupling_info["external_dependencies"]
        chunk.references = coupling_info["internal_dependencies"]
        return chunk

    def _merge_related_chunks(self, chunks: list[CodeChunk], _source: bytes,
        ) -> list[CodeChunk]:
        """Merge chunks that are semantically related."""
        if not chunks:
            return chunks
        merged = []
        skip_indices = set()
        for i, chunk1 in enumerate(chunks):
            if i in skip_indices:
                continue
            merge_candidates = []
            for j, chunk2 in enumerate(chunks[i + 1:], i + 1):
                if j in skip_indices:
                    continue
                if self._should_merge_chunks(chunk1, chunk2):
                    merge_candidates.append((j, chunk2))
                    skip_indices.add(j)
            if merge_candidates:
                merged_chunk = self._merge_chunks([chunk1] + [c for _, c in
                    merge_candidates])
                merged.append(merged_chunk)
            else:
                merged.append(chunk1)
        return merged

    def _should_merge_chunks(self, chunk1: CodeChunk, chunk2: CodeChunk,
        ) -> bool:
        """Determine if two chunks should be merged based on semantic relationships."""
        total_lines = chunk1.end_line - chunk1.start_line + 1 + (chunk2.
            end_line - chunk2.start_line + 1)
        if total_lines > self.config["max_chunk_size"]:
            return False
        for node_types in self.cohesive_groups.values():
            if (chunk1.node_type in node_types and chunk2.node_type in
                node_types):
                return True
        if hasattr(chunk1, "metadata") and hasattr(chunk2, "metadata"):
            sem1 = chunk1.metadata.get("semantic", {})
            sem2 = chunk2.metadata.get("semantic", {})
            if sem1.get("role") == sem2.get("role"):
                return True
            deps1 = set(chunk1.dependencies)
            deps2 = set(chunk2.dependencies)
            if deps1 and deps2 and len(deps1 & deps2) > len(deps1 ^ deps2):
                return True
        if chunk2.start_line - chunk1.end_line <= 2 and hasattr(chunk1,
            "metadata") and hasattr(chunk2, "metadata"):
            comp1 = chunk1.metadata.get("complexity", {}).get("score", 0)
            comp2 = chunk2.metadata.get("complexity", {}).get("score", 0)
            if comp1 < 5 and comp2 < 5:
                return True
        return False

    def _split_complex_chunks(self, chunks: list[CodeChunk], ast: Node,
        source: bytes, file_path: str, language: str) -> list[CodeChunk]:
        """Split chunks that are too complex into smaller, cohesive pieces."""
        result = []
        for chunk in chunks:
            if not hasattr(chunk, "metadata"):
                result.append(chunk)
                continue
            complexity = chunk.metadata.get("complexity", {}).get("score", 0)
            line_count = chunk.end_line - chunk.start_line + 1
            should_split = complexity > self.config["complexity_threshold"
                ] * 2 or line_count > self.config["max_chunk_size"]
            if should_split:
                chunk_node = self._find_node_at_position(ast, chunk.
                    byte_start, chunk.byte_end)
                if chunk_node:
                    sub_chunks = self._split_node(chunk_node, source,
                        file_path, language, chunk)
                    result.extend(sub_chunks)
                else:
                    result.append(chunk)
            else:
                result.append(chunk)
        return result

    def _split_node(self, node: Node, source: bytes, file_path: str,
        language: str, parent_chunk: CodeChunk) -> list[CodeChunk]:
        """Split a complex node into smaller chunks."""
        sub_chunks = []
        split_points = self._find_split_points(node, source)
        if not split_points:
            return [parent_chunk]
        for i, (start_node, end_node) in enumerate(split_points):
            content = source[start_node.start_byte:end_node.end_byte].decode(
                "utf-8", errors="replace")
            sub_chunk = CodeChunk(language=language, file_path=file_path,
                node_type=f"{parent_chunk.node_type}_part_{i + 1}",
                start_line=start_node.start_point[0] + 1, end_line=end_node
                .end_point[0] + 1, byte_start=start_node.start_byte,
                byte_end=end_node.end_byte, parent_context=parent_chunk.
                parent_context, content=content, parent_chunk_id=parent_chunk.chunk_id)
            sub_metadata = {"semantic": self.semantic_analyzer.
                analyze_semantics(start_node, source), "complexity": self.
                complexity_analyzer.calculate_complexity(start_node, source)}
            sub_chunk.metadata = sub_metadata
            sub_chunks.append(sub_chunk)
        return sub_chunks

    def _find_split_points(self, node: Node, _source: bytes) -> list[tuple[
        Node, Node]]:
        """Find logical points to split a complex node."""
        split_points = []
        natural_boundaries = {"if_statement", "while_statement",
            "for_statement", "try_statement", "switch_statement",
            "case_clause", "function_definition", "method_definition",
            "block_statement", "compound_statement"}
        boundary_nodes = []

        def find_boundaries(n: Node):
            if n.type in natural_boundaries:
                boundary_nodes.append(n)
            for child in n.children:
                find_boundaries(child)
        find_boundaries(node)
        if boundary_nodes:
            current_start = boundary_nodes[0]
            current_end = boundary_nodes[0]
            for i in range(1, len(boundary_nodes)):
                next_node = boundary_nodes[i]
                lines_in_current = current_end.end_point[0
                    ] - current_start.start_point[0] + 1
                if lines_in_current > self.config["max_chunk_size"] // 2:
                    split_points.append((current_start, current_end))
                    current_start = next_node
                current_end = next_node
            split_points.append((current_start, current_end))
        return split_points

    def _optimize_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Final optimization pass to ensure chunk quality."""
        optimized = []
        for chunk in chunks:
            line_count = chunk.end_line - chunk.start_line + 1
            if line_count < self.config["min_chunk_size"]:
                if chunk.node_type in self.semantic_boundaries:
                    optimized.append(chunk)
                continue
            if not chunk.parent_context and hasattr(chunk, "metadata"):
                semantic = chunk.metadata.get("semantic", {})
                chunk.parent_context = semantic.get("role", "unknown")
            optimized.append(chunk)
        return optimized

    def _determine_parent_context(self, node: Node, _source: bytes) -> str:
        """Determine the parent context for a chunk."""
        parent = node.parent
        while parent:
            if parent.type in self.semantic_boundaries:
                for child in parent.children:
                    if child.type == "identifier":
                        return f"{parent.type}: {child.text.decode()}"
                return parent.type
            parent = parent.parent
        return "module"

    @staticmethod
    def _find_node_at_position(root: Node, start_byte: int, end_byte: int,
        ) -> Node:
        """Find the node at the given byte position."""

        def search(node: Node) -> Node:
            if node.start_byte == start_byte and node.end_byte == end_byte:
                return node
            for child in node.children:
                if (child.start_byte <= start_byte and child.end_byte >=
                    end_byte):
                    result = search(child)
                    if result:
                        return result
            return None
        return search(root)

    @classmethod
    def _merge_chunks(cls, chunks: list[CodeChunk]) -> CodeChunk:
        """Merge multiple chunks into a single chunk."""
        if not chunks:
            return None
        chunks.sort(key=lambda c: c.start_line)
        first = chunks[0]
        last = chunks[-1]
        combined_content = "\n\n".join(c.content for c in chunks)
        merged_metadata = {"semantic": {"role": "merged", "patterns": []},
            "complexity": {"score": 0}}
        for chunk in chunks:
            if hasattr(chunk, "metadata"):
                patterns = chunk.metadata.get("semantic", {}).get("patterns",
                    [])
                merged_metadata["semantic"]["patterns"].extend(patterns)
                merged_metadata["complexity"]["score"] += chunk.metadata.get(
                    "complexity", {}).get("score", 0)
        merged = CodeChunk(language=first.language, file_path=first.
            file_path, node_type="merged_chunk", start_line=first.
            start_line, end_line=last.end_line, byte_start=first.byte_start,
            byte_end=last.byte_end, parent_context=first.parent_context,
            content=combined_content)
        merged.metadata = merged_metadata
        all_deps = set()
        all_refs = set()
        for chunk in chunks:
            all_deps.update(chunk.dependencies)
            all_refs.update(chunk.references)
        merged.dependencies = list(all_deps)
        merged.references = list(all_refs)
        return merged
