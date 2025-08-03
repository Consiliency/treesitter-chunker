"""GraphML export implementation for code chunks."""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.dom import minidom

from .graph_exporter_base import GraphEdge, GraphExporterBase, GraphNode


class GraphMLExporter(GraphExporterBase):
    """Export code chunks as GraphML format for use in graph visualization tools."""

    def __init__(self):
        super().__init__()
        self.graph_attrs: dict[str, Any] = {"edgedefault": "directed", "id":
            "CodeGraph"}
        self.node_attrs: dict[str, str] = {}
        self.edge_attrs: dict[str, str] = {}

    def _register_attributes(self) -> None:
        """Register all unique attributes from nodes and edges."""
        for node in self.nodes.values():
            for key, value in node.properties.items():
                if key not in self.node_attrs:
                    self.node_attrs[key] = self._infer_type(value)
        for edge in self.edges:
            for key, value in edge.properties.items():
                if key not in self.edge_attrs:
                    self.edge_attrs[key] = self._infer_type(value)

    @staticmethod
    def _infer_type(value: Any) -> str:
        """Infer GraphML data type from Python value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "double"
        return "string"

    def _create_key_elements(self, root: ET.Element) -> None:
        """Create key elements for all attributes."""
        for attr_name, attr_type in self.node_attrs.items():
            key = ET.SubElement(root, "key")
            key.set("id", f"n_{attr_name}")
            key.set("for", "node")
            key.set("attr.name", attr_name)
            key.set("attr.type", attr_type)
        for attr_name, attr_type in self.edge_attrs.items():
            key = ET.SubElement(root, "key")
            key.set("id", f"e_{attr_name}")
            key.set("for", "edge")
            key.set("attr.name", attr_name)
            key.set("attr.type", attr_type)
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

    def _create_node_element(self, graph: ET.Element, node_id: str, node:
        GraphNode) -> None:
        """Create a node element with all its data."""
        node_elem = ET.SubElement(graph, "node")
        node_elem.set("id", node_id)
        data = ET.SubElement(node_elem, "data")
        data.set("key", "n_label")
        data.text = node.label
        for key, value in node.properties.items():
            if key in self.node_attrs:
                data = ET.SubElement(node_elem, "data")
                data.set("key", f"n_{key}")
                data.text = str(value)

    def _create_edge_element(self, graph: ET.Element, edge: GraphEdge,
        edge_id: int) -> None:
        """Create an edge element with all its data."""
        edge_elem = ET.SubElement(graph, "edge")
        edge_elem.set("id", f"e{edge_id}")
        edge_elem.set("source", edge.source_id)
        edge_elem.set("target", edge.target_id)
        data = ET.SubElement(edge_elem, "data")
        data.set("key", "e_label")
        data.text = edge.relationship_type
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
        self._register_attributes()
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation",
            "http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd",
            )
        self._create_key_elements(root)
        graph = ET.SubElement(root, "graph")
        for attr, value in self.graph_attrs.items():
            graph.set(attr, str(value))
        for node_id, node in self.nodes.items():
            self._create_node_element(graph, node_id, node)
        for i, edge in enumerate(self.edges):
            self._create_edge_element(graph, edge, i)
        if pretty_print:
            rough_string = ET.tostring(root, encoding="unicode")
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        return ET.tostring(root, encoding="unicode")

    def export(self, output_path: Path, pretty_print: bool = True, **options,
        ) -> None:
        """Export the graph to a GraphML file.

        Args:
            output_path: Path to write the GraphML file
            pretty_print: Whether to format the XML with indentation
            **options: Additional options
        """
        graphml_content = self.export_string(pretty_print=pretty_print, **
            options)
        output_path.write_text(graphml_content, encoding="utf-8")

    def add_visualization_hints(self, node_colors: (dict[str, str] | None) =
        None, edge_colors: (dict[str, str] | None) = None, node_shapes: (dict
        [str, str] | None) = None) -> None:
        """Add visualization hints for graph rendering tools.

        Args:
            node_colors: Dict mapping chunk types to colors (e.g., {"function": "#FF0000"})
            edge_colors: Dict mapping relationship types to colors
            node_shapes: Dict mapping chunk types to shapes (e.g., {"class": "rectangle"})
        """
        if node_colors:
            self.node_attrs["color"] = "string"
            for node in self.nodes.values():
                chunk_type = node.properties.get("chunk_type", "unknown")
                if chunk_type in node_colors:
                    node.properties["color"] = node_colors[chunk_type]
        if node_shapes:
            self.node_attrs["shape"] = "string"
            for node in self.nodes.values():
                chunk_type = node.properties.get("chunk_type", "unknown")
                if chunk_type in node_shapes:
                    node.properties["shape"] = node_shapes[chunk_type]
        if edge_colors:
            self.edge_attrs["color"] = "string"
            for edge in self.edges:
                if edge.relationship_type in edge_colors:
                    edge.properties["color"] = edge_colors[edge.
                        relationship_type]
