"""GraphML export implementation for code chunks."""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import Dict, Any, List, Optional
from .graph_exporter_base import GraphExporterBase, GraphNode, GraphEdge
from ..types import CodeChunk


class GraphMLExporter(GraphExporterBase):
    """Export code chunks as GraphML format for use in graph visualization tools."""
    
    def __init__(self):
        super().__init__()
        self.graph_attrs: Dict[str, Any] = {
            "edgedefault": "directed",
            "id": "CodeGraph"
        }
        # Track attribute keys for GraphML schema
        self.node_attrs: Dict[str, str] = {}
        self.edge_attrs: Dict[str, str] = {}
    
    def _register_attributes(self) -> None:
        """Register all unique attributes from nodes and edges."""
        # Collect all unique node attributes
        for node in self.nodes.values():
            for key, value in node.properties.items():
                if key not in self.node_attrs:
                    self.node_attrs[key] = self._infer_type(value)
        
        # Collect all unique edge attributes
        for edge in self.edges:
            for key, value in edge.properties.items():
                if key not in self.edge_attrs:
                    self.edge_attrs[key] = self._infer_type(value)
    
    def _infer_type(self, value: Any) -> str:
        """Infer GraphML data type from Python value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "double"
        else:
            return "string"
    
    def _create_key_elements(self, root: ET.Element) -> None:
        """Create key elements for all attributes."""
        # Node attributes
        for attr_name, attr_type in self.node_attrs.items():
            key = ET.SubElement(root, "key")
            key.set("id", f"n_{attr_name}")
            key.set("for", "node")
            key.set("attr.name", attr_name)
            key.set("attr.type", attr_type)
        
        # Edge attributes
        for attr_name, attr_type in self.edge_attrs.items():
            key = ET.SubElement(root, "key")
            key.set("id", f"e_{attr_name}")
            key.set("for", "edge")
            key.set("attr.name", attr_name)
            key.set("attr.type", attr_type)
        
        # Add standard attributes
        key = ET.SubElement(root, "key")
        key.set("id", "n_label")
        key.set("for", "node")
        key.set("attr.name", "label")
        key.set("attr.type", "string")
        
        key = ET.SubElement(root, "key")
        key.set("id", "e_label")
        key.set("for", "edge")
        key.set("attr.name", "label")
        key.set("attr.type", "string")
    
    def _create_node_element(self, graph: ET.Element, node_id: str, node: GraphNode) -> None:
        """Create a node element with all its data."""
        node_elem = ET.SubElement(graph, "node")
        node_elem.set("id", node_id)
        
        # Add label
        data = ET.SubElement(node_elem, "data")
        data.set("key", "n_label")
        data.text = node.label
        
        # Add all properties
        for key, value in node.properties.items():
            if key in self.node_attrs:
                data = ET.SubElement(node_elem, "data")
                data.set("key", f"n_{key}")
                data.text = str(value)
    
    def _create_edge_element(self, graph: ET.Element, edge: GraphEdge, edge_id: int) -> None:
        """Create an edge element with all its data."""
        edge_elem = ET.SubElement(graph, "edge")
        edge_elem.set("id", f"e{edge_id}")
        edge_elem.set("source", edge.source_id)
        edge_elem.set("target", edge.target_id)
        
        # Add label (relationship type)
        data = ET.SubElement(edge_elem, "data")
        data.set("key", "e_label")
        data.text = edge.relationship_type
        
        # Add all properties
        for key, value in edge.properties.items():
            if key in self.edge_attrs:
                data = ET.SubElement(edge_elem, "data")
                data.set("key", f"e_{key}")
                data.text = str(value)
    
    def export_string(self, pretty_print: bool = True, **options) -> str:
        """Export the graph as a GraphML string.
        
        Args:
            pretty_print: Whether to format the XML with indentation
            **options: Additional options (unused)
            
        Returns:
            GraphML representation as a string
        """
        # Register all attributes
        self._register_attributes()
        
        # Create root element
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation", 
                "http://graphml.graphdrawing.org/xmlns "
                "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd")
        
        # Create key elements
        self._create_key_elements(root)
        
        # Create graph element
        graph = ET.SubElement(root, "graph")
        for attr, value in self.graph_attrs.items():
            graph.set(attr, str(value))
        
        # Add nodes
        for node_id, node in self.nodes.items():
            self._create_node_element(graph, node_id, node)
        
        # Add edges
        for i, edge in enumerate(self.edges):
            self._create_edge_element(graph, edge, i)
        
        # Convert to string
        if pretty_print:
            rough_string = ET.tostring(root, encoding='unicode')
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        else:
            return ET.tostring(root, encoding='unicode')
    
    def export(self, output_path: Path, pretty_print: bool = True, **options) -> None:
        """Export the graph to a GraphML file.
        
        Args:
            output_path: Path to write the GraphML file
            pretty_print: Whether to format the XML with indentation
            **options: Additional options
        """
        graphml_content = self.export_string(pretty_print=pretty_print, **options)
        output_path.write_text(graphml_content, encoding='utf-8')
    
    def add_visualization_hints(self, node_colors: Optional[Dict[str, str]] = None,
                              edge_colors: Optional[Dict[str, str]] = None,
                              node_shapes: Optional[Dict[str, str]] = None) -> None:
        """Add visualization hints for graph rendering tools.
        
        Args:
            node_colors: Dict mapping chunk types to colors (e.g., {"function": "#FF0000"})
            edge_colors: Dict mapping relationship types to colors
            node_shapes: Dict mapping chunk types to shapes (e.g., {"class": "rectangle"})
        """
        # Add color attribute for nodes
        if node_colors:
            self.node_attrs["color"] = "string"
            for node in self.nodes.values():
                if node.chunk.chunk_type in node_colors:
                    node.properties["color"] = node_colors[node.chunk.chunk_type]
        
        # Add shape attribute for nodes
        if node_shapes:
            self.node_attrs["shape"] = "string"
            for node in self.nodes.values():
                if node.chunk.chunk_type in node_shapes:
                    node.properties["shape"] = node_shapes[node.chunk.chunk_type]
        
        # Add color attribute for edges
        if edge_colors:
            self.edge_attrs["color"] = "string"
            for edge in self.edges:
                if edge.relationship_type in edge_colors:
                    edge.properties["color"] = edge_colors[edge.relationship_type]