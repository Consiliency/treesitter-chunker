"""DOT (Graphviz) export implementation for code chunks."""

from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from .graph_exporter_base import GraphExporterBase, GraphNode, GraphEdge
from ..types import CodeChunk


class DotExporter(GraphExporterBase):
    """Export code chunks as DOT format for Graphviz visualization."""
    
    def __init__(self):
        super().__init__()
        self.graph_attrs: Dict[str, str] = {
            "rankdir": "TB",  # Top to bottom layout
            "fontname": "Arial",
            "fontsize": "10",
            "compound": "true"  # Allow edges between clusters
        }
        self.node_attrs: Dict[str, str] = {
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "lightblue",
            "fontname": "Arial",
            "fontsize": "10"
        }
        self.edge_attrs: Dict[str, str] = {
            "fontname": "Arial",
            "fontsize": "8"
        }
        # Style mappings for different chunk types
        self.chunk_type_styles: Dict[str, Dict[str, str]] = {
            "class": {"shape": "box", "fillcolor": "lightgreen", "style": "filled"},
            "function": {"shape": "ellipse", "fillcolor": "lightblue", "style": "filled"},
            "method": {"shape": "ellipse", "fillcolor": "lightyellow", "style": "filled"},
            "module": {"shape": "tab", "fillcolor": "lightgray", "style": "filled"},
            "import": {"shape": "note", "fillcolor": "pink", "style": "filled"},
        }
        # Edge styles for different relationship types
        self.edge_type_styles: Dict[str, Dict[str, str]] = {
            "CONTAINS": {"style": "solid", "color": "black"},
            "IMPORTS": {"style": "dashed", "color": "blue"},
            "CALLS": {"style": "dotted", "color": "red"},
            "INHERITS": {"style": "solid", "color": "green", "arrowhead": "empty"},
        }
    
    def _escape_label(self, text: str) -> str:
        """Escape text for DOT labels."""
        # Escape special characters
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        return text
    
    def _format_node_id(self, node_id: str) -> str:
        """Format node ID for DOT syntax."""
        # Replace special characters with underscores
        safe_id = node_id.replace(':', '_').replace('/', '_').replace('.', '_')
        safe_id = safe_id.replace('-', '_').replace(' ', '_')
        return f'"{safe_id}"'
    
    def _get_node_attributes(self, node: GraphNode) -> Dict[str, str]:
        """Get attributes for a node based on its type."""
        attrs = self.node_attrs.copy()
        
        # Apply chunk type specific styles
        chunk_type = node.chunk.metadata.get("chunk_type", node.chunk.node_type) if node.chunk.metadata else node.chunk.node_type
        if chunk_type and chunk_type in self.chunk_type_styles:
            attrs.update(self.chunk_type_styles[chunk_type])
        
        # Create label
        label_parts = []
        chunk_type = node.chunk.metadata.get("chunk_type") if node.chunk.metadata else None
        chunk_type = chunk_type or node.chunk.node_type or "chunk"
        
        if node.chunk.metadata and "name" in node.chunk.metadata:
            label_parts.append(f"{node.chunk.metadata['name']} ({chunk_type})")
        else:
            label_parts.append(chunk_type)
        
        # Add file location
        label_parts.append(f"{node.chunk.file_path}:{node.chunk.start_line}-{node.chunk.end_line}")
        
        # Add additional metadata
        if node.chunk.metadata:
            if "complexity" in node.chunk.metadata:
                label_parts.append(f"Complexity: {node.chunk.metadata['complexity']}")
            if "token_count" in node.chunk.metadata:
                label_parts.append(f"Tokens: {node.chunk.metadata['token_count']}")
        
        attrs["label"] = self._escape_label("\\n".join(label_parts))
        
        return attrs
    
    def _get_edge_attributes(self, edge: GraphEdge) -> Dict[str, str]:
        """Get attributes for an edge based on its type."""
        attrs = self.edge_attrs.copy()
        
        # Apply relationship type specific styles
        if edge.relationship_type in self.edge_type_styles:
            attrs.update(self.edge_type_styles[edge.relationship_type])
        
        # Set label
        attrs["label"] = edge.relationship_type
        
        # Add properties as tooltip
        if edge.properties:
            tooltip_parts = [f"{k}: {v}" for k, v in edge.properties.items()]
            attrs["tooltip"] = self._escape_label("; ".join(tooltip_parts))
        
        return attrs
    
    def _format_attributes(self, attrs: Dict[str, str]) -> str:
        """Format attributes for DOT syntax."""
        if not attrs:
            return ""
        
        attr_parts = []
        for key, value in attrs.items():
            attr_parts.append(f'{key}="{value}"')
        
        return f" [{', '.join(attr_parts)}]"
    
    def export_string(self, use_clusters: bool = True, **options) -> str:
        """Export the graph as a DOT string.
        
        Args:
            use_clusters: Whether to group nodes by file/module
            **options: Additional options
            
        Returns:
            DOT representation as a string
        """
        lines = []
        
        # Start graph
        lines.append("digraph CodeGraph {")
        
        # Graph attributes
        for key, value in self.graph_attrs.items():
            lines.append(f'  {key}="{value}";')
        
        # Default node attributes
        lines.append(f"  node{self._format_attributes(self.node_attrs)};")
        
        # Default edge attributes
        lines.append(f"  edge{self._format_attributes(self.edge_attrs)};")
        
        lines.append("")
        
        if use_clusters:
            # Group nodes by file/module
            clusters = self.get_subgraph_clusters()
            
            for cluster_idx, (cluster_name, node_ids) in enumerate(clusters.items()):
                lines.append(f"  subgraph cluster_{cluster_idx} {{")
                lines.append(f'    label="{self._escape_label(cluster_name)}";')
                lines.append('    style="rounded,filled";')
                lines.append('    fillcolor="lightgray";')
                lines.append('    color="black";')
                lines.append("")
                
                # Add nodes in this cluster
                for node_id in node_ids:
                    if node_id in self.nodes:
                        node = self.nodes[node_id]
                        attrs = self._get_node_attributes(node)
                        lines.append(f"    {self._format_node_id(node_id)}{self._format_attributes(attrs)};")
                
                lines.append("  }")
                lines.append("")
            
            # Add nodes not in any cluster
            clustered_nodes = set()
            for node_ids in clusters.values():
                clustered_nodes.update(node_ids)
            
            for node_id, node in self.nodes.items():
                if node_id not in clustered_nodes:
                    attrs = self._get_node_attributes(node)
                    lines.append(f"  {self._format_node_id(node_id)}{self._format_attributes(attrs)};")
        else:
            # Add all nodes without clustering
            for node_id, node in self.nodes.items():
                attrs = self._get_node_attributes(node)
                lines.append(f"  {self._format_node_id(node_id)}{self._format_attributes(attrs)};")
        
        lines.append("")
        
        # Add edges
        for edge in self.edges:
            attrs = self._get_edge_attributes(edge)
            source = self._format_node_id(edge.source_id)
            target = self._format_node_id(edge.target_id)
            lines.append(f"  {source} -> {target}{self._format_attributes(attrs)};")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def export(self, output_path: Path, use_clusters: bool = True, **options) -> None:
        """Export the graph to a DOT file.
        
        Args:
            output_path: Path to write the DOT file
            use_clusters: Whether to group nodes by file/module
            **options: Additional options
        """
        dot_content = self.export_string(use_clusters=use_clusters, **options)
        output_path.write_text(dot_content, encoding='utf-8')
    
    def set_graph_attribute(self, key: str, value: str) -> None:
        """Set a graph-level attribute."""
        self.graph_attrs[key] = value
    
    def set_node_style(self, chunk_type: str, **style_attrs) -> None:
        """Set style attributes for a specific chunk type.
        
        Args:
            chunk_type: The chunk type to style
            **style_attrs: DOT style attributes (e.g., shape="box", fillcolor="red")
        """
        if chunk_type not in self.chunk_type_styles:
            self.chunk_type_styles[chunk_type] = {}
        self.chunk_type_styles[chunk_type].update(style_attrs)
    
    def set_edge_style(self, relationship_type: str, **style_attrs) -> None:
        """Set style attributes for a specific relationship type.
        
        Args:
            relationship_type: The relationship type to style
            **style_attrs: DOT style attributes (e.g., style="dashed", color="blue")
        """
        if relationship_type not in self.edge_type_styles:
            self.edge_type_styles[relationship_type] = {}
        self.edge_type_styles[relationship_type].update(style_attrs)