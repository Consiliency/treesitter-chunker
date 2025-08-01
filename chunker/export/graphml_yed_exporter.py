"""Extended GraphML exporter with yEd support for enhanced visualization."""
import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom

from .graphml_exporter import GraphMLExporter


class GraphMLyEdExporter(GraphMLExporter):
    """GraphML exporter with yEd extensions for better visualization in yEd graph editor."""

    def __init__(self):
        super().__init__()
        self.default_node_styles = {"function": {"shape": "roundrectangle",
            "fill": "#4287f5", "border": "#2e5db8", "text": "#ffffff"},
            "class": {"shape": "rectangle", "fill": "#42f554", "border":
            "#2eb83a", "text": "#000000"}, "method": {"shape": "ellipse",
            "fill": "#f5a442", "border": "#b87a2e", "text": "#000000"},
            "module": {"shape": "hexagon", "fill": "#f542d7", "border":
            "#b82ea1", "text": "#ffffff"}}
        self.default_edge_styles = {"CALLS": {"color": "#ff0000", "style":
            "line", "width": "2.0"}, "IMPORTS": {"color": "#0000ff",
            "style": "dashed", "width": "1.5"}, "CONTAINS": {"color":
            "#00ff00", "style": "dotted", "width": "1.0"}}

    @staticmethod
    def _create_key_elements(root: ET.Element) -> None:
        """Create key elements including yEd-specific attributes."""
        super()._create_key_elements(root)
        key = ET.SubElement(root, "key")
        key.set("for", "node")
        key.set("id", "d6")
        key.set("yfiles.type", "nodegraphics")
        key = ET.SubElement(root, "key")
        key.set("for", "edge")
        key.set("id", "d10")
        key.set("yfiles.type", "edgegraphics")

    def _create_node_element(self, graph: ET.Element, node_id: str, node: Any,
        ) -> None:
        """Create a node element with yEd graphics."""
        node_elem = ET.SubElement(graph, "node")
        node_elem.set("id", node_id)
        super()._create_node_element(graph, node_id, node)
        data = ET.SubElement(node_elem, "data")
        data.set("key", "d6")
        shape_node = ET.SubElement(data, "y:ShapeNode")
        geometry = ET.SubElement(shape_node, "y:Geometry")
        geometry.set("height", "60.0")
        geometry.set("width", "120.0")
        geometry.set("x", "0.0")
        geometry.set("y", "0.0")
        chunk_type = node.properties.get("chunk_type", "unknown")
        style = self.default_node_styles.get(chunk_type, self.
            default_node_styles.get("function"))
        fill = ET.SubElement(shape_node, "y:Fill")
        fill.set("color", style["fill"])
        fill.set("transparent", "false")
        border = ET.SubElement(shape_node, "y:BorderStyle")
        border.set("color", style["border"])
        border.set("type", "line")
        border.set("width", "2.0")
        label = ET.SubElement(shape_node, "y:NodeLabel")
        label.set("alignment", "center")
        label.set("autoSizePolicy", "content")
        label.set("fontFamily", "Arial")
        label.set("fontSize", "12")
        label.set("textColor", style["text"])
        label.text = f"{node.label}\\n{node.properties.get('name', '')}"
        shape = ET.SubElement(shape_node, "y:Shape")
        shape.set("type", style["shape"])

    def _create_edge_element(self, graph: ET.Element, edge: Any, edge_id: int,
        ) -> None:
        """Create an edge element with yEd graphics."""
        edge_elem = ET.SubElement(graph, "edge")
        edge_elem.set("id", f"e{edge_id}")
        edge_elem.set("source", edge.source_id)
        edge_elem.set("target", edge.target_id)
        super()._create_edge_element(graph, edge, edge_id)
        data = ET.SubElement(edge_elem, "data")
        data.set("key", "d10")
        poly_edge = ET.SubElement(data, "y:PolyLineEdge")
        style = self.default_edge_styles.get(edge.relationship_type, self.
            default_edge_styles.get("CALLS"))
        line_style = ET.SubElement(poly_edge, "y:LineStyle")
        line_style.set("color", style["color"])
        line_style.set("type", style["style"])
        line_style.set("width", style["width"])
        arrows = ET.SubElement(poly_edge, "y:Arrows")
        arrows.set("source", "none")
        arrows.set("target", "standard")
        label = ET.SubElement(poly_edge, "y:EdgeLabel")
        label.set("alignment", "center")
        label.set("fontFamily", "Arial")
        label.set("fontSize", "10")
        label.text = edge.relationship_type

    def export_string(self, pretty_print: bool = True, use_yed: bool = True, **
        options) -> str:
        """Export with optional yEd extensions.

        Args:
            pretty_print: Whether to format the XML
            use_yed: Whether to include yEd extensions
            **options: Additional options

        Returns:
            GraphML string with optional yEd extensions
        """
        if use_yed:
            self._register_attributes()
            root = ET.Element("graphml")
            root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
            root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            root.set("xmlns:y", "http://www.yworks.com/xml/graphml")
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
        return super().export_string(pretty_print=pretty_print, **options)
