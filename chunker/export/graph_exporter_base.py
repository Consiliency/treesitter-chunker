"""Base class for graph export functionality."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
from ..types import CodeChunk


class GraphNode:
    """Represents a node in the graph."""
    
    def __init__(self, chunk: CodeChunk):
        self.id = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
        self.chunk = chunk
        # Get chunk_type from metadata if available, otherwise use node_type
        chunk_type = chunk.metadata.get("chunk_type", chunk.node_type) if chunk.metadata else chunk.node_type
        self.label = chunk_type or "unknown"
        self.properties: Dict[str, Any] = {
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "chunk_type": chunk_type,
            "language": chunk.language,
        }
        if chunk.metadata:
            self.properties.update(chunk.metadata)


class GraphEdge:
    """Represents an edge between nodes in the graph."""
    
    def __init__(self, source_id: str, target_id: str, relationship_type: str, properties: Optional[Dict[str, Any]] = None):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.properties = properties or {}


class GraphExporterBase(ABC):
    """Base class for exporting code chunks as graph data."""
    
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
    
    def add_chunks(self, chunks: List[CodeChunk]) -> None:
        """Add chunks as nodes to the graph."""
        for chunk in chunks:
            node = GraphNode(chunk)
            self.nodes[node.id] = node
    
    def add_relationship(self, source_chunk: CodeChunk, target_chunk: CodeChunk, 
                        relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Add a relationship between two chunks."""
        source_node = GraphNode(source_chunk)
        target_node = GraphNode(target_chunk)
        edge = GraphEdge(source_node.id, target_node.id, relationship_type, properties)
        self.edges.append(edge)
    
    def extract_relationships(self, chunks: List[CodeChunk]) -> None:
        """Extract relationships between chunks based on their metadata and structure.
        
        This base implementation extracts:
        - Parent-child relationships from hierarchy metadata
        - Import/dependency relationships
        - Call relationships
        
        Subclasses can override to add more relationship types.
        """
        chunk_map = {self._get_chunk_id(chunk): chunk for chunk in chunks}
        
        for chunk in chunks:
            # Extract parent-child relationships
            if chunk.metadata and "parent_id" in chunk.metadata:
                parent_id = chunk.metadata["parent_id"]
                if parent_id in chunk_map:
                    self.add_relationship(
                        chunk_map[parent_id], 
                        chunk, 
                        "CONTAINS",
                        {"relationship_source": "hierarchy"}
                    )
            
            # Extract import relationships
            if chunk.metadata and "imports" in chunk.metadata:
                for import_info in chunk.metadata["imports"]:
                    # Find chunks that might be imported
                    for target_chunk in chunks:
                        if self._matches_import(import_info, target_chunk):
                            self.add_relationship(
                                chunk,
                                target_chunk,
                                "IMPORTS",
                                {"import_name": import_info}
                            )
            
            # Extract call relationships
            if chunk.metadata and "calls" in chunk.metadata:
                for call_info in chunk.metadata["calls"]:
                    for target_chunk in chunks:
                        if self._matches_call(call_info, target_chunk):
                            self.add_relationship(
                                chunk,
                                target_chunk,
                                "CALLS",
                                {"call_name": call_info}
                            )
    
    def _get_chunk_id(self, chunk: CodeChunk) -> str:
        """Generate a unique ID for a chunk."""
        return f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
    
    def _matches_import(self, import_name: str, chunk: CodeChunk) -> bool:
        """Check if an import name matches a chunk."""
        # Simple implementation - can be overridden for language-specific matching
        if chunk.metadata and "name" in chunk.metadata:
            return chunk.metadata["name"] == import_name
        return False
    
    def _matches_call(self, call_name: str, chunk: CodeChunk) -> bool:
        """Check if a call name matches a chunk."""
        # Simple implementation - can be overridden for language-specific matching
        if chunk.metadata and "name" in chunk.metadata:
            return chunk.metadata["name"] == call_name
        return False
    
    def get_subgraph_clusters(self) -> Dict[str, List[str]]:
        """Group nodes into clusters (e.g., by file or module).
        
        Returns a dict mapping cluster names to lists of node IDs.
        """
        clusters: Dict[str, List[str]] = {}
        for node_id, node in self.nodes.items():
            file_path = str(node.chunk.file_path)
            if file_path not in clusters:
                clusters[file_path] = []
            clusters[file_path].append(node_id)
        return clusters
    
    @abstractmethod
    def export(self, output_path: Path, **options) -> None:
        """Export the graph to the specified format.
        
        Args:
            output_path: Path to write the output file
            **options: Format-specific options
        """
        raise NotImplementedError("Subclasses must implement export()")
    
    @abstractmethod
    def export_string(self, **options) -> str:
        """Export the graph as a string in the specified format.
        
        Args:
            **options: Format-specific options
            
        Returns:
            The graph representation as a string
        """
        raise NotImplementedError("Subclasses must implement export_string()")