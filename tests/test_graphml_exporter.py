"""Unit tests for GraphML exporter."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chunker.export.graphml_exporter import GraphMLExporter
from chunker.types import CodeChunk


class TestGraphMLExporter:
    """Test GraphML export functionality."""

    @pytest.fixture()
    def sample_chunk(self):
        """Create a sample code chunk."""
        return CodeChunk(
            file_path="test.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=50,
            content="def test():\n    pass",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={"name": "test", "chunk_type": "function"},
        )

    @pytest.fixture()
    def exporter(self):
        """Create a GraphMLExporter instance."""
        return GraphMLExporter()

    def test_xml_namespace(self, exporter, sample_chunk):
        """Test that proper XML namespace is used."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()

        root = ET.fromstring(xml_str)
        assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"
        assert "http://graphml.graphdrawing.org/xmlns" in root.attrib.get(
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
            "",
        )

    def test_graph_attributes(self, exporter, sample_chunk):
        """Test graph element attributes."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()

        root = ET.fromstring(xml_str)
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")

        assert graph is not None
        assert graph.get("edgedefault") == "directed"
        assert graph.get("id") == "CodeGraph"

    def test_key_elements(self, exporter, sample_chunk):
        """Test that key elements are properly defined."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()

        root = ET.fromstring(xml_str)
        keys = root.findall(".//{http://graphml.graphdrawing.org/xmlns}key")

        # Check for standard keys
        key_ids = {key.get("id") for key in keys}
        assert "n_label" in key_ids
        assert "e_label" in key_ids

        # Check key attributes
        node_keys = [k for k in keys if k.get("for") == "node"]
        edge_keys = [k for k in keys if k.get("for") == "edge"]

        assert len(node_keys) > 0
        assert len(edge_keys) >= 1  # At least label key

    def test_node_data_elements(self, exporter, sample_chunk):
        """Test node data elements."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()

        root = ET.fromstring(xml_str)
        nodes = root.findall(".//{http://graphml.graphdrawing.org/xmlns}node")

        assert len(nodes) == 1
        node = nodes[0]

        # Check node ID
        assert node.get("id") == "test.py:1:5"

        # Check data elements
        data_elements = node.findall(".//{http://graphml.graphdrawing.org/xmlns}data")
        data_dict = {d.get("key"): d.text for d in data_elements}

        assert data_dict["n_label"] == "function"
        assert data_dict["n_file_path"] == "test.py"
        assert data_dict["n_start_line"] == "1"
        assert data_dict["n_end_line"] == "5"

    def test_edge_creation(self, exporter):
        """Test edge creation and data."""
        chunk1 = CodeChunk(
            file_path="a.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=50,
            content="def a(): pass",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={"chunk_type": "function"},
        )
        chunk2 = CodeChunk(
            file_path="b.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=50,
            content="def b(): pass",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={"chunk_type": "function"},
        )

        exporter.add_chunks([chunk1, chunk2])
        exporter.add_relationship(chunk1, chunk2, "CALLS", {"line": 3})

        xml_str = exporter.export_string()
        root = ET.fromstring(xml_str)

        edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(edges) == 1

        edge = edges[0]
        assert edge.get("source") == "a.py:1:5"
        assert edge.get("target") == "b.py:1:5"

        # Check edge data
        data_elements = edge.findall(".//{http://graphml.graphdrawing.org/xmlns}data")
        data_dict = {d.get("key"): d.text for d in data_elements}

        assert data_dict["e_label"] == "CALLS"
        assert data_dict["e_line"] == "3"

    def test_special_character_escaping(self, exporter):
        """Test that special XML characters are properly escaped."""
        chunk = CodeChunk(
            file_path="test.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            content='def test():\n    """Test <tag> & "quotes"."""\n    return x > 5 & y < 10',
            node_type="function",
            language="python",
            parent_context="module",
            metadata={
                "name": "test",
                "chunk_type": "function",
                "description": "Test <tag> & special chars",
            },
        )

        exporter.add_chunks([chunk])
        xml_str = exporter.export_string()

        # Ensure XML is parseable
        root = ET.fromstring(xml_str)

        # Check that special chars are in the raw XML
        assert "&lt;" in xml_str  # <
        assert "&gt;" in xml_str  # >
        assert "&amp;" in xml_str  # &
        assert (
            "&quot;" in xml_str or '"' in xml_str
        )  # quotes might not be escaped in text content

    def test_export_to_file(self, exporter, sample_chunk):
        """Test exporting to a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.graphml"

            exporter.add_chunks([sample_chunk])
            exporter.export(output_path)

            assert output_path.exists()

            # Verify it's valid XML
            tree = ET.parse(output_path)
            root = tree.getroot()
            assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"

    def test_visualization_hints_integration(self, exporter):
        """Test visualization hints are properly added."""
        chunks = [
            CodeChunk(
                file_path="test.py",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=50,
                content="def f(): pass",
                node_type="function",
                language="python",
                parent_context="module",
                metadata={"chunk_type": "function"},
            ),
            CodeChunk(
                file_path="test.py",
                start_line=10,
                end_line=20,
                byte_start=100,
                byte_end=200,
                content="class C: pass",
                node_type="class",
                language="python",
                parent_context="module",
                metadata={"chunk_type": "class"},
            ),
        ]

        exporter.add_chunks(chunks)
        exporter.add_relationship(chunks[0], chunks[1], "USED_BY", {})

        # Add visualization hints
        exporter.add_visualization_hints(
            node_colors={"function": "#FF0000", "class": "#00FF00"},
            edge_colors={"USED_BY": "#0000FF"},
            node_shapes={"function": "ellipse", "class": "rectangle"},
        )

        xml_str = exporter.export_string()
        root = ET.fromstring(xml_str)

        # Check that color/shape keys exist
        keys = root.findall(".//{http://graphml.graphdrawing.org/xmlns}key")
        key_names = {k.get("attr.name") for k in keys}

        assert "color" in key_names
        assert "shape" in key_names

        # Check node properties
        nodes = root.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        for node in nodes:
            data_elements = node.findall(
                ".//{http://graphml.graphdrawing.org/xmlns}data",
            )
            data_dict = {d.get("key"): d.text for d in data_elements}

            if data_dict.get("n_chunk_type") == "function":
                assert data_dict.get("n_color") == "#FF0000"
                assert data_dict.get("n_shape") == "ellipse"
            elif data_dict.get("n_chunk_type") == "class":
                assert data_dict.get("n_color") == "#00FF00"
                assert data_dict.get("n_shape") == "rectangle"

    def test_pretty_print_option(self, exporter, sample_chunk):
        """Test pretty print vs compact output."""
        exporter.add_chunks([sample_chunk])

        # Pretty printed
        pretty_xml = exporter.export_string(pretty_print=True)
        assert "\n" in pretty_xml
        assert "  " in pretty_xml  # Indentation

        # Compact
        compact_xml = exporter.export_string(pretty_print=False)
        # Compact might still have newlines from content, but no indentation
        assert "  <" not in compact_xml  # No indented tags

    def test_empty_graph(self, exporter):
        """Test exporting an empty graph."""
        xml_str = exporter.export_string()

        root = ET.fromstring(xml_str)
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")

        nodes = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        edges = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")

        assert len(nodes) == 0
        assert len(edges) == 0
