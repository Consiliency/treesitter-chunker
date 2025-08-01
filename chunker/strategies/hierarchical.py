"""Hierarchical chunking strategy that preserves nested structure relationships."""
from collections import defaultdict
from typing import Any

from tree_sitter import Node

from chunker.interfaces.base import ChunkingStrategy
from chunker.types import CodeChunk


class HierarchicalChunker(ChunkingStrategy):
    """Chunks code while preserving hierarchical relationships.

    Creates a hierarchy of chunks that:
    - Maintains parent-child relationships
    - Preserves nesting structure
    - Allows for tree-based navigation
    - Supports different granularity levels
    """

    def __init__(self):
        self.config = {"max_depth": 5, "min_chunk_size": 5,
            "max_chunk_size": 100, "preserve_leaf_nodes": True,
            "granularity": "balanced", "include_intermediate": True}
        self.hierarchy_levels = {"python": [["module"], ["class_definition",
            "function_definition"], ["method_definition",
            "nested_function_definition"], ["if_statement", "for_statement",
            "while_statement", "with_statement"], ["expression_statement",
            "assignment"]], "javascript": [["program"], [
            "class_declaration", "function_declaration", "export_statement",
            ], ["method_definition", "arrow_function",
            "function_expression"], ["if_statement", "for_statement",
            "while_statement", "switch_statement"], ["expression_statement",
            "variable_declaration"]], "java": [["program"], [
            "class_declaration", "interface_declaration"], [
            "method_declaration", "constructor_declaration"], [
            "if_statement", "for_statement", "while_statement",
            "try_statement"], ["expression_statement",
            "local_variable_declaration"]], "c": [["translation_unit"], [
            "function_definition", "struct_specifier", "enum_specifier"], [
            "compound_statement"], ["if_statement", "for_statement",
            "while_statement", "switch_statement"], ["expression_statement",
            "declaration"]], "rust": [["source_file"], ["impl_item",
            "trait_item", "function_item", "struct_item"], ["function",
            "method"], ["if_expression", "match_expression",
            "loop_expression"], ["expression_statement", "let_declaration"]]}
        self.structural_nodes = {"module", "program", "translation_unit",
            "source_file", "class_definition", "class_declaration",
            "struct_specifier", "interface_declaration", "trait_definition",
            "impl_item", "function_definition", "function_declaration",
            "method_definition", "namespace_definition", "package_declaration"}
        self.atomic_nodes = {"string", "number", "identifier", "comment",
            "import_statement", "include_statement", "decorator", "annotation"}

    def can_handle(self, _file_path: str, language: str) -> bool:
        """Check if language is supported for hierarchical chunking."""
        return language in self.hierarchy_levels

    def chunk(self, ast: Node, source: bytes, file_path: str, language: str,
        ) -> list[CodeChunk]:
        """Create hierarchical chunks from the AST."""
        hierarchy = self._build_hierarchy(ast, source, language)
        chunks = self._extract_hierarchical_chunks(hierarchy, source,
            file_path, language)
        chunks = self._optimize_hierarchy(chunks)
        return chunks

    def configure(self, config: dict[str, Any]) -> None:
        """Update configuration settings."""
        self.config.update(config)

    def _build_hierarchy(self, ast: Node, source: bytes, language: str) -> dict[
        str, Any]:
        """Build a hierarchical representation of the AST."""
        hierarchy = {"node": ast, "level": 0, "children": [], "metadata":
            self._analyze_node(ast, source)}
        levels = self.hierarchy_levels.get(language, [])

        def build_tree(node: Node, parent_dict: dict, depth: int = 0):
            if depth > self.config["max_depth"]:
                return
            node_level = self._get_node_level(node.type, levels)
            if self._should_include_node(node, node_level, depth):
                node_dict = {"node": node, "level": node_level, "depth":
                    depth, "children": [], "metadata": self._analyze_node(
                    node, source)}
                parent_dict["children"].append(node_dict)
                current_parent = node_dict
            else:
                current_parent = parent_dict
            for child in node.children:
                build_tree(child, current_parent, depth + 1)
        for child in ast.children:
            build_tree(child, hierarchy, 1)
        return hierarchy

    @staticmethod
    def _get_node_level(node_type: str, levels: list[list[str]]) -> int:
        """Determine the hierarchical level of a node type."""
        for i, level_types in enumerate(levels):
            if node_type in level_types:
                return i
        return len(levels)

    def _should_include_node(self, node: Node, level: int, _depth: int) -> bool:
        """Determine if a node should be included in the hierarchy."""
        if node.type in self.structural_nodes:
            return True
        if node.type in self.atomic_nodes and not self.config[
            "preserve_leaf_nodes"]:
            return False
        line_count = node.end_point[0] - node.start_point[0] + 1
        if line_count < self.config["min_chunk_size"] and not self.config[
            "preserve_leaf_nodes"]:
            return False
        if self.config["granularity"] == "fine":
            return True
        if self.config["granularity"] == "coarse":
            return level <= 2
        return level <= 3 or line_count >= self.config["min_chunk_size"] * 2

    def _analyze_node(self, node: Node, _source: bytes) -> dict[str, Any]:
        """Analyze node properties for metadata."""
        line_count = node.end_point[0] - node.start_point[0] + 1
        child_types = defaultdict(int)
        for child in node.children:
            child_types[child.type] += 1
        name = self._extract_node_name(node)
        return {"name": name, "line_count": line_count, "child_count": len(
            node.children), "child_types": dict(child_types), "has_errors":
            node.has_error}

    def _extract_hierarchical_chunks(hierarchy: dict, source: bytes,
        file_path: str, language: str) -> list[CodeChunk]:
        """Extract chunks from the hierarchy tree."""
        chunks = []
        chunk_map = {}

        def extract_chunks(node_dict: dict, parent_chunk: (CodeChunk | None
            ) = None):
            node = node_dict["node"]
            if not self._should_create_chunk(node, node_dict):
                for child_dict in node_dict["children"]:
                    extract_chunks(child_dict, parent_chunk)
                return
            chunk = self._create_chunk_from_node(node, source, file_path,
                language, parent_chunk, node_dict["metadata"])
            if chunk:
                chunks.append(chunk)
                chunk_map[id(node)] = chunk
                chunk.metadata = chunk.metadata or {}
                chunk.metadata["hierarchy_level"] = node_dict["level"]
                chunk.metadata["hierarchy_depth"] = node_dict["depth"]
                for child_dict in node_dict["children"]:
                    extract_chunks(child_dict, chunk)
            else:
                for child_dict in node_dict["children"]:
                    extract_chunks(child_dict, parent_chunk)
        for child_dict in hierarchy["children"]:
            extract_chunks(child_dict)
        return chunks

    def _should_create_chunk(self, node: Node, node_dict: dict) -> bool:
        """Determine if a node should become a chunk."""
        metadata = node_dict["metadata"]
        if node.type in self.structural_nodes:
            return True
        line_count = metadata["line_count"]
        if line_count < self.config["min_chunk_size"]:
            if not node_dict["children"] and self.config["preserve_leaf_nodes"
                ]:
                return node.type not in self.atomic_nodes
            return False
        if self.config["include_intermediate"]:
            return True
        significant_children = sum(1 for child in node_dict["children"] if
            child["metadata"]["line_count"] >= self.config["min_chunk_size"])
        return significant_children == 0

    @classmethod
    def _create_chunk_from_node(cls, node: Node, source: bytes, file_path:
        str, language: str, parent_chunk: (CodeChunk | None), metadata:
        dict[str, Any]) -> (CodeChunk | None):
        """Create a chunk from a hierarchy node."""
        content = source[node.start_byte:node.end_byte].decode("utf-8",
            errors="replace")
        if parent_chunk:
            context = (
                f"{parent_chunk.node_type}: {parent_chunk.metadata.get('name', '')}"
                )
        else:
            context = "root"
        chunk = CodeChunk(language=language, file_path=file_path, node_type=node.type, start_line=node.start_point[0] + 1, end_line=node.
            end_point[0] + 1, byte_start=node.start_byte, byte_end=node.
            end_byte, parent_context=context, content=content,
            parent_chunk_id=parent_chunk.chunk_id if parent_chunk else None)
        chunk.metadata = {"name": metadata["name"], "child_count": metadata
            ["child_count"], "line_count": metadata["line_count"]}
        return chunk

    def _optimize_hierarchy(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Optimize the hierarchical chunk structure."""
        optimized = []
        parent_map = defaultdict(list)
        for chunk in chunks:
            if chunk.parent_chunk_id:
                parent_map[chunk.parent_chunk_id].append(chunk)
        for chunk in chunks:
            children = parent_map.get(chunk.chunk_id, [])
            if self._should_split_chunk(chunk, children):
                split_chunks = self._split_hierarchical_chunk(chunk, children)
                optimized.extend(split_chunks)
            elif self._should_merge_chunk(chunk, children):
                merged = self._merge_with_children(chunk, children)
                optimized.append(merged)
                for child in children:
                    if child in chunks:
                        chunks.remove(child)
            else:
                optimized.append(chunk)
        return optimized

    def _should_split_chunk(self, chunk: CodeChunk, children: list[CodeChunk],
        ) -> bool:
        """Determine if a chunk should be split."""
        line_count = chunk.end_line - chunk.start_line + 1
        if line_count > self.config["max_chunk_size"] and len(children) > 1:
            child_coverage = sum(c.end_line - c.start_line + 1 for c in
                children)
            return child_coverage > line_count * 0.7
        return False

    def _should_merge_chunk(self, chunk: CodeChunk, children: list[CodeChunk],
        ) -> bool:
        """Determine if a chunk should be merged with its children."""
        line_count = chunk.end_line - chunk.start_line + 1
        if line_count > self.config["max_chunk_size"] // 2:
            return False
        if children:
            avg_child_size = sum(c.end_line - c.start_line + 1 for c in
                children) / len(children)
            return avg_child_size < self.config["min_chunk_size"]
        return False

    @staticmethod
    def _split_hierarchical_chunk(chunk: CodeChunk, children: list[CodeChunk],
        ) -> list[CodeChunk]:
        """Split a chunk using its children as boundaries."""
        children.sort(key=lambda c: c.start_line)
        return [chunk, *children]

    @staticmethod
    def _merge_with_children(parent: CodeChunk, children: list[CodeChunk],
        ) -> CodeChunk:
        """Merge a parent chunk with its children."""
        parent.metadata = parent.metadata or {}
        parent.metadata["merged_children"] = len(children)
        parent.metadata["child_types"] = [c.node_type for c in children]
        all_refs = set(parent.references)
        all_deps = set(parent.dependencies)
        for child in children:
            all_refs.update(child.references)
            all_deps.update(child.dependencies)
        parent.references = list(all_refs)
        parent.dependencies = list(all_deps)
        return parent

    @staticmethod
    def _extract_node_name(node: Node) -> str:
        """Extract name from a node if available."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
            if child.type == "property_identifier":
                return child.text.decode()
        if node.type in {"function_definition", "method_definition"}:
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode()
                if child.type == "property_identifier":
                    return child.text.decode()
                for grandchild in child.children:
                    if grandchild.type == "identifier":
                        return grandchild.text.decode()
        return ""
