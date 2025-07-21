"""Main structured export orchestrator with streaming support."""

from __future__ import annotations
import io
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
from datetime import datetime, timezone
import json

from ..interfaces.export import (
    StructuredExporter,
    ExportFormat,
    ExportMetadata,
    ChunkRelationship,
    ExportFilter,
    ExportTransformer
)
from ..types import CodeChunk
from ..exceptions import ChunkerError


class StructuredExportOrchestrator(StructuredExporter):
    """Main orchestrator for structured exports with streaming support."""
    
    def __init__(self):
        self._exporters: Dict[ExportFormat, StructuredExporter] = {}
        self._filters: List[ExportFilter] = []
        self._transformers: List[ExportTransformer] = []
        self._batch_size = 1000  # Default batch size for streaming
        
    def register_exporter(self, format: ExportFormat, exporter: StructuredExporter) -> None:
        """Register an exporter for a specific format.
        
        Args:
            format: Export format
            exporter: Exporter instance
        """
        self._exporters[format] = exporter
        
    def add_filter(self, filter: ExportFilter) -> None:
        """Add a filter to the export pipeline.
        
        Args:
            filter: Filter to add
        """
        self._filters.append(filter)
        
    def add_transformer(self, transformer: ExportTransformer) -> None:
        """Add a transformer to the export pipeline.
        
        Args:
            transformer: Transformer to add
        """
        self._transformers.append(transformer)
        
    def export(self,
               chunks: List[CodeChunk],
               relationships: List[ChunkRelationship],
               output: Union[Path, io.IOBase],
               metadata: Optional[ExportMetadata] = None) -> None:
        """Export chunks with relationships.
        
        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        # Determine format from output path or metadata
        format = self._determine_format(output, metadata)
        
        if format not in self._exporters:
            raise ChunkerError(f"No exporter registered for format: {format}")
            
        # Apply filters
        filtered_chunks = self._apply_chunk_filters(chunks)
        filtered_relationships = self._apply_relationship_filters(relationships)
        
        # Create metadata if not provided
        if metadata is None:
            metadata = self._create_metadata(
                format, filtered_chunks, filtered_relationships
            )
            
        # Delegate to specific exporter - pass original objects, not transformed
        exporter = self._exporters[format]
        exporter.export(
            filtered_chunks,
            filtered_relationships,
            output,
            metadata
        )
        
    def export_streaming(self,
                        chunk_iterator: Iterator[CodeChunk],
                        relationship_iterator: Iterator[ChunkRelationship],
                        output: Union[Path, io.IOBase]) -> None:
        """Export using iterators for large datasets.
        
        Args:
            chunk_iterator: Iterator yielding chunks
            relationship_iterator: Iterator yielding relationships
            output: Output path or stream
        """
        format = self._determine_format(output, None)
        
        if format not in self._exporters:
            raise ChunkerError(f"No exporter registered for format: {format}")
            
        exporter = self._exporters[format]
        
        # Create filtering iterators only - don't transform for streaming
        filtered_chunks = self._filter_chunk_iterator(chunk_iterator)
        filtered_relationships = self._filter_relationship_iterator(relationship_iterator)
        
        # Delegate to specific exporter - pass filtered but not transformed objects
        exporter.export_streaming(
            filtered_chunks,
            filtered_relationships,
            output
        )
        
    def supports_format(self, format: ExportFormat) -> bool:
        """Check if this exporter supports a format.
        
        Args:
            format: Export format to check
            
        Returns:
            True if format is supported
        """
        return format in self._exporters
        
    def get_schema(self) -> Dict[str, Any]:
        """Get the export schema.
        
        Returns:
            Schema definition for this exporter
        """
        return {
            "supported_formats": [f.value for f in self._exporters.keys()],
            "filters": len(self._filters),
            "transformers": len(self._transformers),
            "batch_size": self._batch_size
        }
        
    def set_batch_size(self, size: int) -> None:
        """Set batch size for streaming operations.
        
        Args:
            size: Batch size
        """
        self._batch_size = size
        
    # Private helper methods
    
    def _determine_format(self, 
                         output: Union[Path, io.IOBase],
                         metadata: Optional[ExportMetadata]) -> ExportFormat:
        """Determine export format from output or metadata."""
        # Check metadata first
        if metadata and metadata.format:
            return metadata.format
            
        # Try to determine from file extension
        if isinstance(output, (str, Path)):
            path = Path(output)
            ext = path.suffix.lower()
            
            format_map = {
                '.json': ExportFormat.JSON,
                '.jsonl': ExportFormat.JSONL,
                '.parquet': ExportFormat.PARQUET,
                '.graphml': ExportFormat.GRAPHML,
                '.dot': ExportFormat.DOT,
                '.db': ExportFormat.SQLITE,
                '.sqlite': ExportFormat.SQLITE,
                '.sqlite3': ExportFormat.SQLITE,
                '.cypher': ExportFormat.NEO4J,
                '.cql': ExportFormat.NEO4J,
            }
            
            if ext in format_map:
                return format_map[ext]
                
        raise ChunkerError("Cannot determine export format from output path")
        
    def _apply_chunk_filters(self, chunks: List[CodeChunk]) -> List[CodeChunk]:
        """Apply all filters to chunks."""
        result = chunks
        for filter in self._filters:
            result = [c for c in result if filter.should_include_chunk(c)]
        return result
        
    def _apply_relationship_filters(self, 
                                   relationships: List[ChunkRelationship]) -> List[ChunkRelationship]:
        """Apply all filters to relationships."""
        result = relationships
        for filter in self._filters:
            result = [r for r in result if filter.should_include_relationship(r)]
        return result
        
    def _apply_chunk_transformers(self, chunks: List[CodeChunk]) -> List[Dict[str, Any]]:
        """Apply all transformers to chunks."""
        result = []
        for chunk in chunks:
            transformed = chunk.__dict__.copy()
            for transformer in self._transformers:
                transformed = transformer.transform_chunk(chunk)
            result.append(transformed)
        return result
        
    def _apply_relationship_transformers(self, 
                                       relationships: List[ChunkRelationship]) -> List[Dict[str, Any]]:
        """Apply all transformers to relationships."""
        result = []
        for rel in relationships:
            transformed = {
                'source_chunk_id': rel.source_chunk_id,
                'target_chunk_id': rel.target_chunk_id,
                'relationship_type': rel.relationship_type.value,
                'metadata': rel.metadata or {}
            }
            for transformer in self._transformers:
                transformed = transformer.transform_relationship(rel)
            result.append(transformed)
        return result
        
    def _create_metadata(self,
                        format: ExportFormat,
                        chunks: List[Any],
                        relationships: List[Any]) -> ExportMetadata:
        """Create export metadata."""
        source_files = list(set(
            c.file_path if hasattr(c, 'file_path') else c.get('file_path', '')
            for c in chunks
        ))
        
        return ExportMetadata(
            format=format,
            version="1.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_files=source_files,
            chunk_count=len(chunks),
            relationship_count=len(relationships),
            options={
                "filters": len(self._filters),
                "transformers": len(self._transformers),
                "batch_size": self._batch_size
            }
        )
        
    def _filter_chunk_iterator(self, 
                              iterator: Iterator[CodeChunk]) -> Iterator[CodeChunk]:
        """Create a filtering iterator for chunks."""
        for chunk in iterator:
            should_include = all(
                filter.should_include_chunk(chunk) 
                for filter in self._filters
            )
            if should_include:
                yield chunk
                
    def _filter_relationship_iterator(self,
                                    iterator: Iterator[ChunkRelationship]) -> Iterator[ChunkRelationship]:
        """Create a filtering iterator for relationships."""
        for rel in iterator:
            should_include = all(
                filter.should_include_relationship(rel)
                for filter in self._filters
            )
            if should_include:
                yield rel
                
    def _transform_chunk_iterator(self,
                                 iterator: Iterator[CodeChunk]) -> Iterator[Dict[str, Any]]:
        """Create a transforming iterator for chunks."""
        for chunk in iterator:
            transformed = chunk.__dict__.copy()
            for transformer in self._transformers:
                transformed = transformer.transform_chunk(chunk)
            yield transformed
            
    def _transform_relationship_iterator(self,
                                       iterator: Iterator[ChunkRelationship]) -> Iterator[Dict[str, Any]]:
        """Create a transforming iterator for relationships."""
        for rel in iterator:
            transformed = {
                'source_chunk_id': rel.source_chunk_id,
                'target_chunk_id': rel.target_chunk_id,
                'relationship_type': rel.relationship_type.value,
                'metadata': rel.metadata or {}
            }
            for transformer in self._transformers:
                transformed = transformer.transform_relationship(rel)
            yield transformed