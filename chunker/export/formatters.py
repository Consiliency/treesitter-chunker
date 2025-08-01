"""JSON schema formatters for different export styles."""
from enum import Enum
from typing import Any, Protocol

from chunker.types import CodeChunk


class SchemaType(Enum):
    """Available JSON schema types."""
    FLAT = "flat"
    NESTED = "nested"
    MINIMAL = "minimal"
    FULL = "full"


class Formatter(Protocol):
    """Protocol for chunk formatters."""

    @staticmethod
    def format(_chunks: list[CodeChunk]) -> Any:
        """Format chunks according to the schema."""
        ...


class FlatFormatter:
    """Formats chunks as a flat array with relationships preserved."""

    def format(self, chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        return [self._chunk_to_dict(chunk) for chunk in chunks]

    @staticmethod
    def _chunk_to_dict(chunk: CodeChunk) -> dict[str, Any]:
        return {"chunk_id": chunk.chunk_id, "language": chunk.language,
            "file_path": chunk.file_path, "node_type": chunk.node_type,
            "start_line": chunk.start_line, "end_line": chunk.end_line,
            "byte_start": chunk.byte_start, "byte_end": chunk.byte_end,
            "parent_context": chunk.parent_context, "parent_chunk_id":
            chunk.parent_chunk_id, "references": chunk.references,
            "dependencies": chunk.dependencies, "content": chunk.content}


class NestedFormatter:
    """Formats chunks as a nested tree structure."""

    def format(self, chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        chunk_map = {c.chunk_id: c for c in chunks}
        children_map: dict[str, list[CodeChunk]] = {}
        roots = []
        for chunk in chunks:
            if chunk.parent_chunk_id and chunk.parent_chunk_id in chunk_map:
                children_map.setdefault(chunk.parent_chunk_id, []).append(chunk,
                    )
            else:
                roots.append(chunk)
        return [self._build_tree(chunk, children_map) for chunk in roots]

    def _build_tree(self, chunk: CodeChunk, children_map: dict[str, list[
        CodeChunk]]) -> dict[str, Any]:
        result = {"chunk_id": chunk.chunk_id, "language": chunk.language,
            "file_path": chunk.file_path, "node_type": chunk.node_type,
            "start_line": chunk.start_line, "end_line": chunk.end_line,
            "content": chunk.content, "children": []}
        if chunk.chunk_id in children_map:
            result["children"] = [self._build_tree(child, children_map) for
                child in children_map[chunk.chunk_id]]
        return result


class MinimalFormatter:
    """Formats only essential chunk information."""

    @staticmethod
    def format(chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        return [{"id": chunk.chunk_id, "type": chunk.node_type, "file":
            chunk.file_path, "lines":
            f"{chunk.start_line}-{chunk.end_line}", "content": chunk.
            content} for chunk in chunks]


class FullFormatter:
    """Formats all chunk information including metadata."""

    def format(self, chunks: list[CodeChunk]) -> dict[str, Any]:
        return {"metadata": {"total_chunks": len(chunks), "languages": list
            ({c.language for c in chunks}), "files": list({c.file_path for
            c in chunks}), "node_types": list({c.node_type for c in chunks},
            )}, "chunks": [self._chunk_to_dict(chunk) for chunk in chunks],
            "relationships": self._extract_relationships(chunks)}

    @staticmethod
    def _chunk_to_dict(chunk: CodeChunk) -> dict[str, Any]:
        return {"chunk_id": chunk.chunk_id, "language": chunk.language,
            "file_path": chunk.file_path, "node_type": chunk.node_type,
            "start_line": chunk.start_line, "end_line": chunk.end_line,
            "byte_start": chunk.byte_start, "byte_end": chunk.byte_end,
            "parent_context": chunk.parent_context, "parent_chunk_id":
            chunk.parent_chunk_id, "references": chunk.references,
            "dependencies": chunk.dependencies, "content": chunk.content}

    @staticmethod
    def _extract_relationships(chunks: list[CodeChunk]) -> dict[str, Any]:
        parent_child = []
        references = []
        dependencies = []
        for chunk in chunks:
            if chunk.parent_chunk_id:
                parent_child.append({"parent": chunk.parent_chunk_id,
                    "child": chunk.chunk_id})
            references.extend({"from": chunk.chunk_id, "to": ref} for ref in
                chunk.references)
            dependencies.extend({"from": chunk.chunk_id, "to": dep} for dep in
                chunk.dependencies)
        return {"parent_child": parent_child, "references": references,
            "dependencies": dependencies}


def get_formatter(schema_type: SchemaType) -> Formatter:
    """Get formatter for the specified schema type."""
    formatters = {SchemaType.FLAT: FlatFormatter(), SchemaType.NESTED:
        NestedFormatter(), SchemaType.MINIMAL: MinimalFormatter(),
        SchemaType.FULL: FullFormatter()}
    return formatters[schema_type]
