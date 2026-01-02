"""Export chunks and relationships to SemanticGraphBundle format.

SemanticGraphBundle is the input format for semantic-lens, a code
visualization platform. See: https://github.com/[org]/semantic-lens
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    ExportMetadata,
    RelationshipType,
    StructuredExporter,
)

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator

    from chunker.types import CodeChunk


# Maps treesitter-chunker node_type to semantic-lens NodeKind
NODE_KIND_MAP: dict[str, str] = {
    # Direct mappings
    "module": "module",
    "class_definition": "class",
    "class_declaration": "class",
    "interface_declaration": "interface",
    "interface_definition": "interface",
    "trait_definition": "trait",
    "trait_declaration": "trait",
    "function_definition": "function",
    "function_declaration": "function",
    "arrow_function": "function",
    "method_definition": "method",
    "method_declaration": "method",
    "field_definition": "field",
    "field_declaration": "field",
    "property_definition": "property",
    "property_declaration": "property",
    "property_signature": "property",
    # Fallback mappings for common node types
    "lexical_declaration": "property",  # const/let/var
    "variable_declaration": "property",
    "type_alias_declaration": "interface",
    "enum_declaration": "class",
}

# Maps treesitter-chunker RelationshipType to semantic-lens EdgeKind
EDGE_KIND_MAP: dict[RelationshipType, str] = {
    RelationshipType.CALLS: "calls",
    RelationshipType.IMPORTS: "imports",
    RelationshipType.INHERITS: "inherits",
    RelationshipType.IMPLEMENTS: "implements",
    RelationshipType.DEFINES: "defines",
    RelationshipType.USES: "uses",
    RelationshipType.REFERENCES: "uses",
    RelationshipType.HAS_METHOD: "defines",
    RelationshipType.PARENT_CHILD: "defines",
    RelationshipType.DEPENDS_ON: "uses",
}

# Valid semantic-lens node kinds (for validation)
VALID_NODE_KINDS = frozenset(
    [
        "module",
        "class",
        "interface",
        "trait",
        "function",
        "method",
        "field",
        "property",
    ]
)

# Valid semantic-lens edge kinds (for validation)
VALID_EDGE_KINDS = frozenset(
    [
        "defines",
        "imports",
        "calls",
        "inherits",
        "implements",
        "uses",
        "reads",
        "writes",
        "throws",
    ]
)


class SemanticLensExporter(StructuredExporter):
    """Export to SemanticGraphBundle format for semantic-lens visualization.

    SemanticGraphBundle is a JSON format containing:
    - version: Schema version (v1.0)
    - generated_at: ISO 8601 timestamp
    - repo: Optional repository metadata
    - nodes: Code elements (classes, functions, methods, etc.)
    - edges: Relationships (calls, imports, inherits, etc.)
    - annotations: Tags and metadata on nodes
    - patterns: Detected design patterns (empty by default)

    Attributes:
        indent: JSON indentation level (None for compact)
        include_content: Whether to include source code in annotations
        repo_url: Optional repository URL for metadata
        repo_commit: Optional commit hash for metadata
        repo_branch: Optional branch name for metadata
    """

    VERSION = "v1.0"

    def __init__(
        self,
        indent: int | None = 2,
        include_content: bool = False,
        repo_url: str | None = None,
        repo_commit: str | None = None,
        repo_branch: str | None = None,
    ):
        """Initialize SemanticLens exporter.

        Args:
            indent: JSON indentation (None for compact output)
            include_content: Include source code as node annotations
            repo_url: Repository URL for bundle metadata
            repo_commit: Git commit hash (7+ chars)
            repo_branch: Git branch name
        """
        self.indent = indent
        self.include_content = include_content
        self.repo_url = repo_url
        self.repo_commit = repo_commit
        self.repo_branch = repo_branch

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks and relationships to SemanticGraphBundle JSON.

        Args:
            chunks: List of code chunks to export as nodes
            relationships: List of relationships to export as edges
            output: Output file path or stream
            metadata: Optional export metadata
        """
        bundle = self._build_bundle(chunks, relationships, metadata)
        json_str = json.dumps(bundle, indent=self.indent, ensure_ascii=False)

        if isinstance(output, str | Path):
            Path(output).write_text(json_str, encoding="utf-8")
        else:
            output.write(json_str)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators (collects all data due to JSON structure).

        Note: SemanticGraphBundle requires complete structure, so streaming
        collects all data before writing. For true streaming, use JSONL.

        Args:
            chunk_iterator: Iterator yielding code chunks
            relationship_iterator: Iterator yielding relationships
            output: Output file path or stream
        """
        chunks = list(chunk_iterator)
        relationships = list(relationship_iterator)
        self.export(chunks, relationships, output)

    @staticmethod
    def supports_format(fmt: ExportFormat) -> bool:
        """Check if this exporter supports the given format.

        Args:
            fmt: Export format to check

        Returns:
            True if format is SEMANTIC_LENS
        """
        return fmt == ExportFormat.SEMANTIC_LENS

    def get_schema(self) -> dict[str, Any]:
        """Get the SemanticGraphBundle schema description.

        Returns:
            Schema definition dict
        """
        return {
            "format": "semantic_lens",
            "version": self.VERSION,
            "spec": "SemanticGraphBundle",
            "indent": self.indent,
            "include_content": self.include_content,
            "structure": {
                "version": "Schema version string (v1.0)",
                "generated_at": "ISO 8601 timestamp",
                "repo": "Optional repository metadata",
                "nodes": "Array of Node objects",
                "edges": "Array of Edge objects",
                "annotations": "Array of Annotation objects",
                "patterns": "Array of PatternInstance objects",
            },
        }

    def _build_bundle(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        metadata: ExportMetadata | None,
    ) -> dict[str, Any]:
        """Build the complete SemanticGraphBundle structure.

        Args:
            chunks: Code chunks to convert to nodes
            relationships: Relationships to convert to edges
            metadata: Optional export metadata

        Returns:
            Complete bundle dict ready for JSON serialization
        """
        # Build chunk_id -> node_id mapping for edge references
        node_id_map: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []

        for chunk in chunks:
            node = self._chunk_to_node(chunk)
            if node:  # Skip unmapped node types
                nodes.append(node)
                node_id_map[chunk.chunk_id] = node["node_id"]
                if chunk.node_id:
                    node_id_map[chunk.node_id] = node["node_id"]

        edges = [
            edge
            for edge in (
                self._relationship_to_edge(rel, node_id_map) for rel in relationships
            )
            if edge is not None
        ]

        annotations = self._build_annotations(chunks, node_id_map)

        return {
            "version": self.VERSION,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "repo": self._build_repo(metadata),
            "nodes": nodes,
            "edges": edges,
            "annotations": annotations,
            "patterns": [],  # Empty - pattern detection is semantic-lens's job
        }

    def _chunk_to_node(self, chunk: CodeChunk) -> dict[str, Any] | None:
        """Convert a CodeChunk to a SemanticGraphBundle Node.

        Args:
            chunk: The code chunk to convert

        Returns:
            Node dict or None if node_type cannot be mapped
        """
        kind = NODE_KIND_MAP.get(chunk.node_type)
        if kind is None:
            # Try lowercase matching
            kind = NODE_KIND_MAP.get(chunk.node_type.lower())
        if kind is None:
            # Skip unknown node types (e.g., comments, expressions)
            return None

        # Generate stable node_id (minimum 8 chars required)
        node_id = chunk.node_id or chunk.chunk_id
        if len(node_id) < 8:
            node_id = f"{node_id}_{uuid.uuid4().hex[:8]}"

        # Extract name from qualified_route or parent_context
        name = self._extract_name(chunk)

        node: dict[str, Any] = {
            "node_id": node_id,
            "kind": kind,
            "name": name,
            "language": chunk.language,
            "file": chunk.file_path,
            "span": [chunk.byte_start, chunk.byte_end],
        }

        # Optional fields
        if chunk.parent_chunk_id:
            node["parent"] = chunk.parent_chunk_id

        if chunk.qualified_route:
            node["route"] = "::".join(chunk.qualified_route)

        # Extract visibility from metadata if available
        visibility = chunk.metadata.get("visibility")
        if visibility in ("public", "protected", "private"):
            node["visibility"] = visibility
        else:
            node["visibility"] = "unknown"

        # Extract signature from metadata if available
        signature = chunk.metadata.get("signature")
        if signature:
            formatted_sig = self._format_signature(signature)
            if formatted_sig:
                node["signature"] = formatted_sig

        return node

    def _format_signature(self, sig: dict | str | None) -> str | None:
        """Convert signature dict to string representation.

        Args:
            sig: Signature as dict or string

        Returns:
            Formatted signature string or None
        """
        if sig is None:
            return None
        if isinstance(sig, str):
            return sig
        if not isinstance(sig, dict):
            return str(sig)

        # Build parameter list
        params = []
        for p in sig.get("parameters", []):
            param_str = p.get("name", "?")
            if p.get("type"):
                param_str += f": {p['type']}"
            if p.get("default") is not None:
                param_str += f" = {p['default']}"
            params.append(param_str)

        param_list = ", ".join(params)
        return_type = sig.get("return_type") or "void"

        return f"({param_list}) => {return_type}"

    def _relationship_to_edge(
        self,
        rel: ChunkRelationship,
        node_id_map: dict[str, str],
    ) -> dict[str, Any] | None:
        """Convert a ChunkRelationship to a SemanticGraphBundle Edge.

        Args:
            rel: The relationship to convert
            node_id_map: Mapping from chunk_id to node_id

        Returns:
            Edge dict or None if relationship cannot be mapped
        """
        kind = EDGE_KIND_MAP.get(rel.relationship_type)
        if kind is None:
            return None

        # Resolve source and destination node IDs
        src = node_id_map.get(rel.source_chunk_id, rel.source_chunk_id)
        dst = node_id_map.get(rel.target_chunk_id, rel.target_chunk_id)

        # Skip edges to unmapped nodes
        if src not in node_id_map.values() and src == rel.source_chunk_id:
            return None
        if dst not in node_id_map.values() and dst == rel.target_chunk_id:
            return None

        # Generate edge_id (minimum 8 chars required)
        edge_id = f"e_{uuid.uuid4().hex[:12]}"

        # Extract confidence from metadata or default to 1.0
        confidence = 1.0
        if rel.metadata and "confidence" in rel.metadata:
            confidence = float(rel.metadata["confidence"])

        edge: dict[str, Any] = {
            "edge_id": edge_id,
            "kind": kind,
            "src": src,
            "dst": dst,
            "confidence": confidence,
            "evidence": ["chunker"],  # Evidence source
        }

        # Include relationship metadata if present
        if rel.metadata:
            edge["meta"] = {
                k: v
                for k, v in rel.metadata.items()
                if k != "confidence"  # Already used above
            }

        return edge

    def _build_annotations(
        self,
        chunks: list[CodeChunk],
        node_id_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Build annotations from chunk metadata.

        Args:
            chunks: Code chunks with potential metadata
            node_id_map: Mapping from chunk_id to node_id

        Returns:
            List of Annotation dicts
        """
        annotations = []

        for chunk in chunks:
            node_id = node_id_map.get(chunk.chunk_id)
            if not node_id:
                continue

            tags = []
            kv: dict[str, Any] = {}

            # Add node_type as tag
            tags.append(f"type:{chunk.node_type}")

            # Include content as annotation if requested
            if self.include_content and chunk.content:
                kv["content_lines"] = chunk.end_line - chunk.start_line + 1

            # Extract tags from metadata
            if chunk.metadata:
                if "tags" in chunk.metadata:
                    tags.extend(chunk.metadata["tags"])
                # Copy select metadata to kv (must be scalar values)
                for key in ("lines", "tokens"):
                    if key in chunk.metadata:
                        val = chunk.metadata[key]
                        # Only include scalar values (string, number, boolean, null)
                        if isinstance(val, (str, int, float, bool)) or val is None:
                            kv[key] = val

                # Handle complexity specially - extract cyclomatic as primary metric
                if "complexity" in chunk.metadata:
                    complexity = chunk.metadata["complexity"]
                    if isinstance(complexity, dict):
                        # Extract cyclomatic complexity as the primary metric
                        kv["complexity"] = complexity.get("cyclomatic", 0)
                    elif isinstance(complexity, (int, float)):
                        kv["complexity"] = complexity

            if tags or kv:
                annotation: dict[str, Any] = {
                    "target_id": node_id,
                    "tags": tags,
                }
                if kv:
                    annotation["kv"] = kv
                annotations.append(annotation)

        return annotations

    def _build_repo(
        self,
        metadata: ExportMetadata | None,
    ) -> dict[str, str] | None:
        """Build repository metadata section.

        Args:
            metadata: Export metadata potentially containing repo info

        Returns:
            Repo dict or None if no repo info available
        """
        # Use explicit repo settings if provided
        if self.repo_url and self.repo_commit:
            repo = {
                "url": self.repo_url,
                "commit": self.repo_commit,
            }
            if self.repo_branch:
                repo["branch"] = self.repo_branch
            return repo

        # Try to extract from export metadata
        if metadata and metadata.source_files:
            # Generate placeholder repo info from source files
            return None  # No repo info available

        return None

    def _extract_name(self, chunk: CodeChunk) -> str:
        """Extract the symbol name from a chunk.

        Args:
            chunk: Code chunk to extract name from

        Returns:
            Symbol name or fallback
        """
        # Try qualified_route first (last segment is the name)
        if chunk.qualified_route:
            last = chunk.qualified_route[-1]
            # Format is "node_type:name" or just "name"
            if ":" in last:
                return last.split(":", 1)[1]
            return last

        # Try parent_context
        if chunk.parent_context:
            # parent_context often contains the name
            parts = chunk.parent_context.split(".")
            if parts:
                return parts[-1]

        # Try metadata
        if "name" in chunk.metadata:
            return str(chunk.metadata["name"])
        if "symbol" in chunk.metadata:
            return str(chunk.metadata["symbol"])

        # Fallback to node_type with line number
        return f"{chunk.node_type}@{chunk.start_line}"
