"""Unit tests for GraphML exporter."""

import csv
import io
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chunker import chunk_file, get_parser
from chunker.export.dot_exporter import DotExporter
from chunker.export.graph_exporter_base import GraphNode, UnifiedGraphNode
from chunker.export.graphml_exporter import GraphMLExporter
from chunker.export.graphml_yed_exporter import GraphMLyEdExporter
from chunker.export.neo4j_exporter import Neo4jExporter
from chunker.types import CodeChunk


class TestGraphMLExporter:
    """Test GraphML export functionality."""

    @pytest.fixture
    def sample_chunk(self):
        """Create a sample code chunk."""
        return CodeChunk(
            file_path="test.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=50,
            content="""def test():
    pass""",
            node_type="function",
            language="python",
            parent_context="module",
            metadata={"name": "test", "chunk_type": "function"},
        )

    @pytest.fixture
    def exporter(self):
        """Create a GraphMLExporter instance."""
        return GraphMLExporter()

    @staticmethod
    def test_xml_namespace(exporter, sample_chunk):
        """Test that proper XML namespace is used."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"
        assert "http://graphml.graphdrawing.org/xmlns" in root.attrib.get(
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
            "",
        )

    @staticmethod
    def test_graph_attributes(exporter, sample_chunk):
        """Test graph element attributes."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")
        assert graph is not None
        assert graph.get("edgedefault") == "directed"
        assert graph.get("id") == "CodeGraph"

    @staticmethod
    def test_key_elements(exporter, sample_chunk):
        """Test that key elements are properly defined."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        keys = root.findall(".//{http://graphml.graphdrawing.org/xmlns}key")
        key_ids = {key.get("id") for key in keys}
        assert "n_label" in key_ids
        assert "e_label" in key_ids
        node_keys = [k for k in keys if k.get("for") == "node"]
        edge_keys = [k for k in keys if k.get("for") == "edge"]
        assert len(node_keys) > 0
        assert len(edge_keys) >= 1

    @staticmethod
    def test_node_data_elements(exporter, sample_chunk):
        """Test node data elements."""
        exporter.add_chunks([sample_chunk])
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        nodes = root.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        assert len(nodes) == 1
        node = nodes[0]
        assert node.get("id") == sample_chunk.node_id
        data_elements = node.findall(".//{http://graphml.graphdrawing.org/xmlns}data")
        data_dict = {d.get("key"): d.text for d in data_elements}
        assert data_dict["n_label"] == "function"
        assert data_dict["n_file_path"] == "test.py"
        assert data_dict["n_start_line"] == "1"
        assert data_dict["n_end_line"] == "5"

    @classmethod
    def test_edge_creation(cls, exporter):
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
        root = ET.fromstring(
            xml_str,
        )
        edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(edges) == 1
        edge = edges[0]
        assert edge.get("source") == chunk1.node_id
        assert edge.get("target") == chunk2.node_id
        data_elements = edge.findall(".//{http://graphml.graphdrawing.org/xmlns}data")
        data_dict = {d.get("key"): d.text for d in data_elements}
        assert data_dict["e_label"] == "CALLS"
        assert data_dict["e_line"] == "3"

    @classmethod
    def test_special_character_escaping(cls, exporter):
        """Test that special XML characters are properly escaped."""
        chunk = CodeChunk(
            file_path="test.py",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            content="""def test():
    ""\"Test <tag> & "quotes".""\"
    return x > 5 & y < 10""",
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
        ET.fromstring(xml_str)
        assert "&lt;" in xml_str
        assert "&gt;" in xml_str
        assert "&amp;" in xml_str
        assert "&quot;" in xml_str or '"' in xml_str

    @classmethod
    def test_export_to_file(cls, exporter, sample_chunk):
        """Test exporting to a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.graphml"
            exporter.add_chunks([sample_chunk])
            exporter.export(output_path)
            assert output_path.exists()
            tree = ET.parse(output_path)
            root = tree.getroot()
            assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"

    @classmethod
    def test_visualization_hints_integration(cls, exporter):
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
        exporter.add_visualization_hints(
            node_colors={"function": "#FF0000", "class": "#00FF00"},
            edge_colors={"USED_BY": "#0000FF"},
            node_shapes={"function": "ellipse", "class": "rectangle"},
        )
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        keys = root.findall(".//{http://graphml.graphdrawing.org/xmlns}key")
        key_names = {k.get("attr.name") for k in keys}
        assert "color" in key_names
        assert "shape" in key_names
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

    @staticmethod
    def test_pretty_print_option(exporter, sample_chunk):
        """Test pretty print vs compact output."""
        exporter.add_chunks([sample_chunk])
        pretty_xml = exporter.export_string(pretty_print=True)
        assert "\n" in pretty_xml
        assert "  " in pretty_xml
        compact_xml = exporter.export_string(pretty_print=False)
        assert "  <" not in compact_xml

    @staticmethod
    def test_empty_graph(exporter):
        """Test exporting an empty graph."""
        xml_str = exporter.export_string()
        root = ET.fromstring(
            xml_str,
        )
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")
        nodes = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        edges = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(nodes) == 0
        assert len(edges) == 0


@pytest.fixture
def parsed_same_span():
    path = Path(__file__).parent / "fixtures/graph_same_span.py"
    assert not get_parser("python").parse(path.read_bytes()).root_node.has_error
    chunks = chunk_file(path, "python")
    spans = {}
    for chunk in chunks:
        span = (chunk.file_path, chunk.start_line, chunk.end_line)
        spans.setdefault(span, set()).add(chunk.node_id)
    assert any(len(ids) >= 2 for ids in spans.values())
    assert len({chunk.node_id for chunk in chunks}) == len(chunks)
    return chunks


@pytest.mark.parametrize(
    "exporter_type", [GraphMLExporter, GraphMLyEdExporter, DotExporter, Neo4jExporter]
)
def test_real_same_span_occurrences_and_endpoints_survive(
    parsed_same_span, exporter_type
):
    chunks = parsed_same_span
    ids = {chunk.node_id for chunk in chunks}
    parents = {chunk.chunk_id: chunk for chunk in chunks}
    expected_defines = {
        (parents[chunk.parent_chunk_id].node_id, chunk.node_id, "DEFINES")
        for chunk in chunks
        if chunk.parent_chunk_id in parents
    }
    assert expected_defines
    observed = []
    for supplied in [
        chunks,
        list(reversed(chunks)),
        chunk_file(Path(chunks[0].file_path), "python"),
    ]:
        exporter = exporter_type()
        exporter.add_chunks(supplied)
        exporter.add_chunks(supplied)
        exporter.add_relationship(chunks[0], chunks[-1], "CALLS")
        exporter.extract_relationships(supplied)
        assert set(exporter.nodes) == ids
        assert {node.to_unified().id for node in exporter.nodes.values()} == ids
        assert {UnifiedGraphNode.from_chunk(chunk).id for chunk in supplied} == ids
        assert {
            node
            for nodes in exporter.get_subgraph_clusters().values()
            for node in nodes
        } == ids
        edges = {
            (e.source_id, e.target_id, e.relationship_type) for e in exporter.edges
        }
        assert expected_defines <= edges
        assert (chunks[0].node_id, chunks[-1].node_id, "CALLS") in edges
        assert all(source in ids and target in ids for source, target, _ in edges)
        observed.append((set(exporter.nodes), edges))
        if exporter_type in [GraphMLExporter, GraphMLyEdExporter]:
            root = ET.fromstring(exporter.export_string())
            xml_ids = {
                node.get("id")
                for node in root.findall(
                    ".//{http://graphml.graphdrawing.org/xmlns}node"
                )
            }
            assert xml_ids == ids
            xml_edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
            assert len(xml_edges) == len(exporter.edges)
            assert all(
                edge.get("source") in ids and edge.get("target") in ids
                for edge in xml_edges
            )
        elif exporter_type is DotExporter:
            output = exporter.export_string(use_clusters=False)
            for node_id in ids:
                assert f'"{node_id}" [' in output
            for source, target, _ in edges:
                assert f'"{source}" -> "{target}"' in output
        else:
            rows = list(
                csv.DictReader(io.StringIO(exporter.export_string(fmt="csv_nodes")))
            )
            assert {row["nodeId:ID"] for row in rows} == ids
            rows = list(
                csv.DictReader(
                    io.StringIO(exporter.export_string(fmt="csv_relationships"))
                )
            )
            assert {
                (row[":START_ID"], row[":END_ID"], row[":TYPE"]) for row in rows
            } == edges
    assert observed[0] == observed[1] == observed[2]


@pytest.mark.parametrize("alias_kind", ["node_id", "chunk_id", "span"])
@pytest.mark.parametrize(
    "exporter_type", [GraphMLExporter, GraphMLyEdExporter, Neo4jExporter]
)
def test_parent_aliases_resolve_unique_real_occurrence(
    parsed_same_span, alias_kind, exporter_type
):
    parent, child = parsed_same_span[:2]
    parent.node_id = 'caller-parent:/path?value="a,b"&other=<x>'
    child.parent_chunk_id = parent.chunk_id
    alias = (
        getattr(parent, alias_kind)
        if alias_kind != "span"
        else f"{parent.file_path}:{parent.start_line}:{parent.end_line}"
    )
    child.metadata = {"parent_id": alias}
    exporter = exporter_type()
    exporter.add_chunks([parent, child])
    exporter.extract_relationships([parent, child])
    ids = {parent.node_id, child.node_id}
    expected_edges = {
        (parent.node_id, child.node_id, "CONTAINS"),
        (parent.node_id, child.node_id, "DEFINES"),
    }
    assert set(exporter.nodes) == ids
    assert {
        (e.source_id, e.target_id, e.relationship_type) for e in exporter.edges
    } == expected_edges
    if exporter_type is Neo4jExporter:
        nodes = list(
            csv.DictReader(io.StringIO(exporter.export_string(fmt="csv_nodes")))
        )
        edges = list(
            csv.DictReader(io.StringIO(exporter.export_string(fmt="csv_relationships")))
        )
        assert {row["nodeId:ID"] for row in nodes} == ids
        assert {
            (row[":START_ID"], row[":END_ID"], row[":TYPE"]) for row in edges
        } == expected_edges
    else:
        root = ET.fromstring(exporter.export_string())
        namespace = "{http://graphml.graphdrawing.org/xmlns}"
        assert {node.get("id") for node in root.findall(f".//{namespace}node")} == ids
        edges = root.findall(f".//{namespace}edge")
        assert len(edges) == len(expected_edges)
        assert {(edge.get("source"), edge.get("target")) for edge in edges} == {
            (source, target) for source, target, _ in expected_edges
        }


@pytest.mark.parametrize("field", ["parent_id", "parent_chunk_id"])
@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_chunk_alias_rejected_before_any_edges(
    parsed_same_span, field, reverse
):
    parent, other, child = parsed_same_span[:3]
    parent.chunk_id = other.chunk_id = "shared-parent"
    for chunk in parsed_same_span:
        chunk.parent_chunk_id = None
        chunk.metadata = {}
    if field == "parent_id":
        child.metadata["parent_id"] = "shared-parent"
    else:
        child.parent_chunk_id = "shared-parent"
    supplied = [parent, other, child]
    if reverse:
        supplied.reverse()
    parent.metadata["calls"] = ["target"]
    other.metadata["name"] = "target"
    exporter = GraphMLExporter()
    exporter.add_chunks(supplied)
    exporter.add_relationship(parent, other, "CALLS")
    before = list(exporter.edges)
    with pytest.raises(ValueError, match=field) as error:
        exporter.extract_relationships(supplied)
    assert "shared-parent" in str(error.value) and "unique" in str(error.value)
    assert exporter.edges == before


@pytest.mark.parametrize("conflict", ["span", "canonical"])
def test_late_ambiguous_parent_cannot_append_partial_edges(parsed_same_span, conflict):
    parent, first, second, child = parsed_same_span[:4]
    for chunk in parsed_same_span:
        chunk.parent_chunk_id = None
        chunk.metadata = {}
    first.metadata = {"parent_id": parent.node_id}
    if conflict == "span":
        alias = f"{second.file_path}:{second.start_line}:{second.end_line}"
    else:
        alias = first.node_id
        second.chunk_id = alias
    child.metadata = {"parent_id": alias}
    exporter = GraphMLExporter()
    exporter.add_chunks(parsed_same_span)
    exporter.add_relationship(parent, child, "CALLS")
    before = list(exporter.edges)
    with pytest.raises(ValueError, match="parent_id"):
        exporter.extract_relationships(parsed_same_span)
    assert exporter.edges == before


def test_exact_alias_precedes_ambiguous_span_and_valid_parents_are_independent(
    parsed_same_span,
):
    parent, other, child = parsed_same_span[:3]
    for chunk in parsed_same_span:
        chunk.parent_chunk_id = None
        chunk.metadata = {}
    alias = f"{other.file_path}:{other.start_line}:{other.end_line}"
    parent.node_id = alias
    child.metadata = {"parent_id": alias}
    child.parent_chunk_id = other.chunk_id
    exporter = GraphMLExporter()
    exporter.add_chunks(parsed_same_span)
    exporter.extract_relationships(parsed_same_span)
    assert {
        (e.source_id, e.target_id, e.relationship_type) for e in exporter.edges
    } == {
        (parent.node_id, child.node_id, "CONTAINS"),
        (other.node_id, child.node_id, "DEFINES"),
    }


def test_duplicate_occurrences_and_unknown_parents_are_harmless(parsed_same_span):
    parent, other, child = parsed_same_span[:3]
    for chunk in parsed_same_span:
        chunk.parent_chunk_id = None
        chunk.metadata = {}
    other.chunk_id = parent.chunk_id
    child.metadata = {"parent_id": "unknown"}
    child.parent_chunk_id = "also-unknown"
    exporter = GraphMLExporter()
    exporter.add_chunks(parsed_same_span + parsed_same_span)
    exporter.add_relationship(parent, child, "CALLS")
    before = list(exporter.edges)
    exporter.extract_relationships(parsed_same_span + parsed_same_span)
    assert exporter.edges == before
    assert set(exporter.nodes) == {chunk.node_id for chunk in parsed_same_span}


def test_repeated_canonical_parent_is_not_ambiguous(parsed_same_span):
    parent, child = parsed_same_span[:2]
    child.metadata = {"parent_id": parent.node_id}
    child.parent_chunk_id = parent.chunk_id
    exporter = GraphMLExporter()
    exporter.extract_relationships([parent, parent, child])
    assert {
        (e.source_id, e.target_id, e.relationship_type) for e in exporter.edges
    } == {
        (parent.node_id, child.node_id, "CONTAINS"),
        (parent.node_id, child.node_id, "DEFINES"),
    }


def test_graph_identity_fallback_does_not_mutate_chunk(parsed_same_span):
    chunk = parsed_same_span[0]
    chunk.node_id = None
    assert GraphNode(chunk).id == chunk.chunk_id
    chunk.chunk_id = None
    assert GraphNode(chunk).id == chunk.generate_id()
    assert chunk.node_id is None and chunk.chunk_id is None
