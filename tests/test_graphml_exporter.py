"""Unit tests for GraphML exporter."""

import copy
import csv
import io
import json
import os
import shlex
import shutil
import subprocess
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
        assert "node_label" in key_ids
        assert "edge_label" in key_ids
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
        assert data_dict["node_label"] == "function"
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
        assert data_dict["edge_label"] == "CALLS"
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


@pytest.mark.parametrize("use_clusters", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize(
    ("caller_ids", "expected_names"),
    [
        (("a-b", "a_b"), {"tc_612d62", "tc_615f62"}),
        (("a:b", "a_b"), None),
        (("a/b", "a_b"), None),
        (("a.b", "a_b"), None),
        (("a b", "a_b"), None),
        (('a"b', "plain"), None),
        (("a\\b", "plain"), None),
        (("a\\", "a"), {"tc_615c", "a"}),
        (("a\nb", "a\rb"), None),
        (("a\tb", "a\x00b"), None),
        (("Σ", "σ"), {"tc_cea3", "tc_cf83"}),
        (("é", "e\u0301"), {"tc_c3a9", "tc_65cc81"}),
        (("a-b", "tc_612d62"), {"tc_612d62", "tc_74635f363132643632"}),
        (("00aF", "00Af"), {"00aF", "00Af"}),
    ],
)
def test_dot_caller_ids_preserve_compiled_graph(
    parsed_same_span, tmp_path, caller_ids, expected_names, use_clusters, file_output
):
    dot = shutil.which("dot")
    if dot is None:
        pytest.skip("Graphviz executable is required for compiled DOT contracts")

    def compile_graph(payload, path=None):
        result = subprocess.run(
            [dot, "-Tjson", *([str(path)] if path is not None else [])],
            input=payload if path is None else None,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout)

    chunks = [
        chunk for chunk in parsed_same_span if chunk.node_type == "function_definition"
    ]
    assert len(chunks) == 2
    assert [chunk.metadata["signature"]["name"] for chunk in chunks] == ["f", "g"]
    parser_ids = [chunk.node_id for chunk in chunks]
    original = [(chunk.chunk_id, chunk.content) for chunk in chunks]
    control = DotExporter()
    control.add_chunks(chunks)
    control.add_relationship(chunks[0], chunks[1], "CALLS")
    reference = compile_graph(control.export_string(use_clusters=use_clusters))
    reference_nodes = reference["objects"][reference.get("_subgraph_cnt", 0) :]
    assert {node["name"] for node in reference_nodes} == set(parser_ids)
    labels = {node["name"]: node["label"] for node in reference_nodes}

    for chunk, caller_id in zip(chunks, caller_ids, strict=True):
        chunk.node_id = caller_id
    exporter = DotExporter()
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], "CALLS")
    assert set(exporter.nodes) == set(caller_ids)
    assert [(edge.source_id, edge.target_id) for edge in exporter.edges] == [caller_ids]
    assert [(chunk.chunk_id, chunk.content) for chunk in chunks] == original
    output = exporter.export_string(use_clusters=use_clusters)
    assert output == exporter.export_string(use_clusters=use_clusters)
    path = tmp_path / "caller.dot" if file_output else None
    if path is not None:
        exporter.export(path, use_clusters=use_clusters)
        output = path.read_text(encoding="utf-8")
        assert output == exporter.export_string(use_clusters=use_clusters)
    graph = compile_graph(output, path)
    cluster_count = graph.get("_subgraph_cnt", 0)
    nodes = graph["objects"][cluster_count:]
    assert len(nodes) == 2
    assert len({node["name"] for node in nodes}) == 2
    if expected_names is not None:
        assert {node["name"] for node in nodes} == expected_names
    by_label = {node["label"]: node["_gvid"] for node in nodes}
    assert set(by_label) == set(labels.values())
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert (edge["tail"], edge["head"]) == (
        by_label[labels[parser_ids[0]]],
        by_label[labels[parser_ids[1]]],
    )
    assert edge["tail"] != edge["head"]
    assert edge["label"] == "CALLS"
    assert cluster_count == int(use_clusters)
    if use_clusters:
        cluster = graph["objects"][0]
        assert cluster["nodes"] == reference["objects"][0]["nodes"]
        assert set(cluster["nodes"]) == {node["_gvid"] for node in nodes}
        assert cluster["label"] == reference["objects"][0]["label"]


@pytest.mark.parametrize("use_clusters", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize(
    ("relationship", "compiled_label"),
    [
        ("CALLS", "CALLS"),
        ("", ""),
        ('CALLS"suffix', 'CALLS"suffix'),
        ('CALLS\\"suffix', 'CALLS\\\\"suffix'),
        ("CALLS\\", "CALLS\\\\"),
        (r"CALLS\N\E\G\T\H\L", r"CALLS\\N\\E\\G\\T\\H\\L"),
        (r"CALLS\n\l\r\t", r"CALLS\\n\\l\\r\\t"),
        (r"CALLS\\suffix", r"CALLS\\\\suffix"),
        ("CALLS\nsuffix", r"CALLS\nsuffix"),
        ("CALLS\rsuffix", "CALLS\rsuffix"),
        ("CALLS\r\nsuffix", "CALLS\r\\nsuffix"),
        ("CALLS\tsuffix", "CALLS\tsuffix"),
        ("Σé", "Σé"),
        ("e\u0301", "e\u0301"),
        ("<b>CALLS</b>", "<b>CALLS</b>"),
    ],
)
def test_dot_relationship_labels_preserve_compiled_text(
    parsed_same_span, tmp_path, relationship, compiled_label, use_clusters, file_output
):
    dot = shutil.which("dot")
    if dot is None:
        pytest.skip("Graphviz executable is required for compiled DOT contracts")

    def compile_graph(payload, format_name, path=None):
        result = subprocess.run(
            [dot, "-T" + format_name, *([str(path)] if path is not None else [])],
            input=payload if path is None else None,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        return result.stdout

    chunks = [
        chunk for chunk in parsed_same_span if chunk.node_type == "function_definition"
    ]
    assert len(chunks) == 2
    assert [chunk.metadata["signature"]["name"] for chunk in chunks] == ["f", "g"]
    ids = [chunk.node_id for chunk in chunks]
    properties = {"note": 'tip"\\tail'}
    control = DotExporter()
    control.add_chunks(chunks)
    control.add_relationship(chunks[0], chunks[1], "CALLS", properties)
    reference = json.loads(
        compile_graph(control.export_string(use_clusters=use_clusters), "json")
    )
    exporter = DotExporter()
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], relationship, properties)
    assert exporter.edges[0].relationship_type == relationship
    assert exporter.edges[0].properties == properties
    output = exporter.export_string(use_clusters=use_clusters)
    assert output == exporter.export_string(use_clusters=use_clusters)
    path = tmp_path / "relationship.dot" if file_output else None
    if path is not None:
        exporter.export(path, use_clusters=use_clusters)
        assert path.read_bytes().replace(b"\r\n", b"\n") == output.encode("utf-8")
    graph = json.loads(compile_graph(output, "json", path))
    cluster_count = graph.get("_subgraph_cnt", 0)
    nodes = graph["objects"][cluster_count:]
    reference_nodes = reference["objects"][reference.get("_subgraph_cnt", 0) :]
    assert len(nodes) == 2
    assert {node["name"] for node in nodes} == set(ids)
    assert {node["name"]: node["label"] for node in nodes} == {
        node["name"]: node["label"] for node in reference_nodes
    }
    node_ids = {node["name"]: node["_gvid"] for node in nodes}
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert (edge["tail"], edge["head"]) == (node_ids[ids[0]], node_ids[ids[1]])
    assert edge["label"] == compiled_label
    assert edge["tooltip"] == reference["edges"][0]["tooltip"]
    if relationship == "CALLS":
        assert edge["color"] == "red"
        assert edge["style"] == "dotted"
    assert cluster_count == int(use_clusters)
    if use_clusters:
        assert graph["objects"][0]["label"] == reference["objects"][0]["label"]
        assert set(graph["objects"][0]["nodes"]) == set(node_ids.values())
    svg = ET.fromstring(compile_graph(output, "svg", path))
    edges = [
        element
        for element in svg.iter("{http://www.w3.org/2000/svg}g")
        if element.get("class") == "edge"
    ]
    assert len(edges) == 1
    rendered = [
        element.text for element in edges[0].iter("{http://www.w3.org/2000/svg}text")
    ]
    assert rendered == (relationship.split("\n") if relationship else [])


@pytest.mark.parametrize("use_clusters", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize(
    ("caller_text", "compiled_tooltip"),
    [
        ("LEFT\tRIGHT", "note: LEFT\tRIGHT"),
        ("\tRIGHT", "note: \tRIGHT"),
        ("LEFT\t", "note: LEFT\t"),
        ("LEFT\t\tRIGHT", "note: LEFT\t\tRIGHT"),
        ("\t", "note: \t"),
        (r"LEFT\tRIGHT", r"note: LEFT\\tRIGHT"),
        ('LEFT"\tRIGHT', 'note: LEFT"\tRIGHT'),
        ("LEFT\\\tRIGHT", "note: LEFT\\\\\tRIGHT"),
        ("Σé\tRIGHT", "note: Σé\tRIGHT"),
        ("LEFT\nRIGHT", r"note: LEFT\nRIGHT"),
        ("LEFT\rRIGHT", r"note: LEFT\rRIGHT"),
        (r"LEFT\nRIGHT", r"note: LEFT\\nRIGHT"),
    ],
)
def test_dot_label_tabs_preserve_compiled_text(
    parsed_same_span, tmp_path, caller_text, compiled_tooltip, use_clusters, file_output
):
    dot = shutil.which("dot")
    if dot is None:
        pytest.skip("Graphviz executable is required for compiled DOT contracts")

    chunks = [
        chunk for chunk in parsed_same_span if chunk.node_type == "function_definition"
    ]
    assert len(chunks) == 2
    assert [chunk.metadata["signature"]["name"] for chunk in chunks] == ["f", "g"]
    ids = [chunk.node_id for chunk in chunks]
    original = [(chunk.chunk_id, chunk.content) for chunk in chunks]
    caller_path = "caller\tfile.py"
    for chunk in chunks:
        chunk.file_path = caller_path
    chunks[0].metadata["name"] = caller_text
    exporter = DotExporter()
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {"note": caller_text})
    assert [(chunk.chunk_id, chunk.content) for chunk in chunks] == original
    assert set(exporter.nodes) == set(ids)
    output = exporter.export_string(use_clusters=use_clusters)
    assert output == exporter.export_string(use_clusters=use_clusters)
    path = tmp_path / "label-tabs.dot" if file_output else None
    if path is not None:
        exporter.export(path, use_clusters=use_clusters)
        assert path.read_bytes().replace(b"\r\n", b"\n") == output.encode("utf-8")

    def compile_graph(format_name):
        result = subprocess.run(
            [dot, "-T" + format_name, *([str(path)] if path is not None else [])],
            input=output if path is None else None,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        return result.stdout

    graph = json.loads(compile_graph("json"))
    cluster_count = graph.get("_subgraph_cnt", 0)
    nodes = graph["objects"][cluster_count:]
    assert len(nodes) == 2
    assert {node["name"] for node in nodes} == set(ids)
    node_ids = {node["name"]: node["_gvid"] for node in nodes}
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert (edge["tail"], edge["head"]) == (node_ids[ids[0]], node_ids[ids[1]])
    assert edge["label"] == "CALLS"
    assert edge["color"] == "red"
    assert edge["style"] == "dotted"
    assert edge["tooltip"] == compiled_tooltip
    assert cluster_count == int(use_clusters)
    if use_clusters:
        assert graph["objects"][0]["label"] == caller_path
        assert set(graph["objects"][0]["nodes"]) == set(node_ids.values())

    svg = ET.fromstring(compile_graph("svg"))
    namespace = "{http://www.w3.org/2000/svg}"
    groups = list(svg.iter(namespace + "g"))
    svg_nodes = [element for element in groups if element.get("class") == "node"]
    assert len(svg_nodes) == 2
    node = next(
        element
        for element in svg_nodes
        if element.find(namespace + "title").text == ids[0]
    )
    svg_edges = [element for element in groups if element.get("class") == "edge"]
    assert len(svg_edges) == 1
    anchors = list(svg_edges[0].iter(namespace + "a"))
    assert len(anchors) == 1
    assert anchors[0].get("{http://www.w3.org/1999/xlink}title") == (
        "note: " + caller_text.replace("\t", " ")
    )
    svg_clusters = [element for element in groups if element.get("class") == "cluster"]
    assert len(svg_clusters) == int(use_clusters)
    if use_clusters:
        assert [
            element.text for element in svg_clusters[0].iter(namespace + "text")
        ] == [caller_path]

    rendered = [element.text for element in node.iter(namespace + "text")]
    caller_lines = caller_text.replace("\r", "\n").split("\n")
    assert rendered == [
        *caller_lines[:-1],
        caller_lines[-1] + " (function_definition)",
        "caller\tfile.py:1-2",
        "Complexity: {'cyclomatic': 1, 'cognitive': 0, 'nesting_depth': 0, "
        "'lines_of_code': 2, 'logical_lines': 2}",
    ]


@pytest.mark.parametrize("use_clusters", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize("extras", ["parsed", "none", "zero", "both"])
@pytest.mark.parametrize(
    (
        "name",
        "kind",
        "caller_path",
        "first_lines",
        "first_json",
        "path_lines",
        "path_json",
    ),
    [
        (
            None,
            "function_definition",
            "caller.py",
            ["function_definition"],
            "function_definition",
            ["caller.py"],
            "caller.py",
        ),
        (
            "",
            "function_definition",
            "caller.py",
            [" (function_definition)"],
            " (function_definition)",
            ["caller.py"],
            "caller.py",
        ),
        (
            "LEFT",
            "function_definition",
            "caller.py",
            ["LEFT (function_definition)"],
            "LEFT (function_definition)",
            ["caller.py"],
            "caller.py",
        ),
        (
            "LEFT\nRIGHT",
            "function_definition",
            "caller.py",
            ["LEFT", "RIGHT (function_definition)"],
            r"LEFT\nRIGHT (function_definition)",
            ["caller.py"],
            "caller.py",
        ),
        (
            r"LEFT\nRIGHT",
            "function_definition",
            "caller.py",
            [r"LEFT\nRIGHT (function_definition)"],
            r"LEFT\\nRIGHT (function_definition)",
            ["caller.py"],
            "caller.py",
        ),
        (
            'LEFT"\\RIGHT',
            "function_definition",
            "caller.py",
            ['LEFT"\\RIGHT (function_definition)'],
            r'LEFT"\\RIGHT (function_definition)',
            ["caller.py"],
            "caller.py",
        ),
        (
            "LEFT\\",
            "function_definition",
            "caller.py",
            ["LEFT\\ (function_definition)"],
            r"LEFT\\ (function_definition)",
            ["caller.py"],
            "caller.py",
        ),
        (
            "Σé",
            "function_definition",
            "Σé.py",
            ["Σé (function_definition)"],
            "Σé (function_definition)",
            ["Σé.py"],
            "Σé.py",
        ),
        (
            None,
            "type\\",
            r"C:\caller\file.py",
            ["type\\"],
            r"type\\",
            [r"C:\caller\file.py"],
            r"C:\\caller\\file.py",
        ),
        (
            "LEFT",
            "function_definition",
            "LEFT\nRIGHT.py",
            ["LEFT (function_definition)"],
            "LEFT (function_definition)",
            ["LEFT", "RIGHT.py"],
            r"LEFT\nRIGHT.py",
        ),
        (
            "LEFT",
            "function_definition",
            r"LEFT\nRIGHT.py",
            ["LEFT (function_definition)"],
            "LEFT (function_definition)",
            [r"LEFT\nRIGHT.py"],
            r"LEFT\\nRIGHT.py",
        ),
        (
            None,
            "function_definition",
            "caller\\",
            ["function_definition"],
            "function_definition",
            ["caller\\"],
            r"caller\\",
        ),
    ],
    ids=[
        "absent",
        "empty",
        "ordinary",
        "name-lf",
        "name-literal-n",
        "quote-slash",
        "name-tail-slash",
        "unicode",
        "kind-tail-slash",
        "path-lf",
        "path-literal-n",
        "path-tail-slash",
    ],
)
def test_dot_generated_node_lines_preserve_compiled_graph(
    parsed_same_span,
    tmp_path,
    name,
    kind,
    caller_path,
    first_lines,
    first_json,
    path_lines,
    path_json,
    extras,
    use_clusters,
    file_output,
):
    dot = shutil.which("dot")
    if dot is None:
        pytest.skip("Graphviz executable is required for compiled DOT contracts")
    chunks = [c for c in parsed_same_span if c.node_type == "function_definition"]
    assert len(chunks) == 2
    assert [c.metadata["signature"]["name"] for c in chunks] == ["f", "g"]
    assert [(c.start_line, c.end_line) for c in chunks] == [(1, 2), (5, 6)]
    ids = [c.node_id for c in chunks]
    assert len(set(ids)) == 2
    complexity = {
        "cyclomatic": 1,
        "cognitive": 0,
        "nesting_depth": 0,
        "lines_of_code": 2,
        "logical_lines": 2,
    }
    complexity_line = (
        "Complexity: {'cyclomatic': 1, 'cognitive': 0, 'nesting_depth': 0, "
        "'lines_of_code': 2, 'logical_lines': 2}"
    )
    for chunk in chunks:
        assert chunk.metadata["complexity"] == complexity
        assert "name" not in chunk.metadata and "chunk_type" not in chunk.metadata
        assert "token_count" not in chunk.metadata
        chunk.file_path = caller_path
        if extras != "parsed":
            chunk.metadata.pop("complexity")
        if extras == "zero":
            chunk.metadata["token_count"] = 0
        if extras == "both":
            chunk.metadata.update(complexity=7, token_count=13)
    chunks[0].node_type = kind
    if name is not None:
        chunks[0].metadata["name"] = name
    metadata_lines = {
        "parsed": [complexity_line],
        "none": [],
        "zero": ["Tokens: 0"],
        "both": ["Complexity: 7", "Tokens: 13"],
    }[extras]
    caller_state = copy.deepcopy([vars(chunk) for chunk in chunks])
    exporter = DotExporter()
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {"note": r"literal\n"})
    node_state = copy.deepcopy(
        {key: (node.label, node.properties) for key, node in exporter.nodes.items()}
    )
    edge_state = copy.deepcopy([vars(edge) for edge in exporter.edges])
    output = exporter.export_string(use_clusters=use_clusters)
    assert output == exporter.export_string(use_clusters=use_clusters)
    path = tmp_path / "generated-lines.dot" if file_output else None
    if path is not None:
        exporter.export(path, use_clusters=use_clusters)
        assert path.read_bytes().replace(b"\r\n", b"\n") == output.encode("utf-8")

    def compile_graph(format_name):
        result = subprocess.run(
            [dot, "-T" + format_name, *([str(path)] if path is not None else [])],
            input=output if path is None else None,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        return result.stdout

    graph = json.loads(compile_graph("json"))
    count = graph.get("_subgraph_cnt", 0)
    nodes = graph["objects"][count:]
    assert len(nodes) == 2 and {node["name"] for node in nodes} == set(ids)
    node_ids = {node["name"]: node["_gvid"] for node in nodes}
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert (edge["tail"], edge["head"]) == (node_ids[ids[0]], node_ids[ids[1]])
    assert edge["label"] == "CALLS" and edge["tooltip"] == r"note: literal\\n"
    assert edge["color"] == "red" and edge["style"] == "dotted"
    assert count == int(use_clusters)
    if use_clusters:
        assert graph["objects"][0]["label"] == path_json
        assert set(graph["objects"][0]["nodes"]) == set(node_ids.values())
    svg = ET.fromstring(compile_graph("svg"))
    namespace = "{http://www.w3.org/2000/svg}"
    groups = list(svg.iter(namespace + "g"))
    svg_nodes = [g for g in groups if g.get("class") == "node"]
    assert len(svg_nodes) == 2
    by_id = {g.find(namespace + "title").text: g for g in svg_nodes}
    assert set(by_id) == set(ids)
    svg_edges = [g for g in groups if g.get("class") == "edge"]
    assert len(svg_edges) == 1
    assert svg_edges[0].find(namespace + "title").text == ids[0] + "->" + ids[1]
    assert [t.text for t in svg_edges[0].iter(namespace + "text")] == ["CALLS"]
    anchors = list(svg_edges[0].iter(namespace + "a"))
    assert (
        len(anchors) == 1
        and anchors[0].get("{http://www.w3.org/1999/xlink}title") == r"note: literal\n"
    )
    clusters = [g for g in groups if g.get("class") == "cluster"]
    assert len(clusters) == int(use_clusters)
    if use_clusters:
        assert [t.text for t in clusters[0].iter(namespace + "text")] == path_lines
    assert [vars(chunk) for chunk in chunks] == caller_state
    assert {
        key: (node.label, node.properties) for key, node in exporter.nodes.items()
    } == node_state
    assert [vars(edge) for edge in exporter.edges] == edge_state
    for index, node_id in enumerate(ids):
        texts = list(by_id[node_id].iter(namespace + "text"))
        assert all(t.get("text-anchor") == "middle" for t in texts)
        span = "1-2" if index == 0 else "5-6"
        expected = [
            *(first_lines if index == 0 else ["function_definition"]),
            *path_lines[:-1],
            path_lines[-1] + ":" + span,
            *metadata_lines,
        ]
        assert [t.text for t in texts] == expected
        expected_json = r"\n".join(
            [
                first_json if index == 0 else "function_definition",
                path_json + ":" + span,
                *metadata_lines,
            ]
        )
        assert (
            next(node for node in nodes if node["name"] == node_id)["label"]
            == expected_json
        )


@pytest.fixture(
    params=[
        pytest.param(
            ("R&amp;D", "R&amp;amp;D", ["R&amp;D"], "R&amp;D"),
            id="entity-named-amp",
        ),
        pytest.param(
            ("A&lt;B&gt;C", "A&amp;lt;B&amp;gt;C", ["A&lt;B&gt;C"], "A&lt;B&gt;C"),
            id="entity-named-markup",
        ),
        pytest.param(
            ("A&quot;B", "A&amp;quot;B", ["A&quot;B"], "A&quot;B"),
            id="entity-named-quote",
        ),
        pytest.param(
            ("A&#10;B", "A&amp;#10;B", ["A&#10;B"], "A&#10;B"),
            id="entity-decimal-lf",
        ),
        pytest.param(
            ("A&#x3a3;B", "A&amp;#x3a3;B", ["A&#x3a3;B"], "A&#x3a3;B"),
            id="entity-hex-unicode",
        ),
        pytest.param(
            ("A&#92;nB", "A&amp;#92;nB", ["A&#92;nB"], "A&#92;nB"),
            id="entity-decimal-slash-n",
        ),
        *[
            pytest.param(
                (
                    "A&#92;" + escape + "B",
                    "A&amp;#92;" + escape + "B",
                    ["A&#92;" + escape + "B"],
                    "A&#92;" + escape + "B",
                ),
                id="entity-decimal-identity-" + escape,
            )
            for escape in ["N", "E", "T", "H", "G", "L"]
        ],
        pytest.param(
            ("A&amp;amp;B", "A&amp;amp;amp;B", ["A&amp;amp;B"], "A&amp;amp;B"),
            id="entity-nested",
        ),
        pytest.param(
            ("A&amp;&#38;B", "A&amp;amp;&amp;#38;B", ["A&amp;&#38;B"], "A&amp;&#38;B"),
            id="entity-adjacent",
        ),
        pytest.param(
            ('A\\"&amp;Σ', r'A\\"&amp;amp;Σ', ['A\\"&amp;Σ'], 'A\\"&amp;Σ'),
            id="entity-quote-slash-unicode",
        ),
        pytest.param(
            ("A&amp;\nB", r"A&amp;amp;\nB", ["A&amp;", "B"], "A&amp;\nB"),
            id="entity-physical-lf",
        ),
        pytest.param(
            ("A&amp;\tB", "A&amp;amp;\tB", ["A&amp;\tB"], "A&amp; B"),
            id="entity-physical-tab",
        ),
        pytest.param(("A&B", "A&amp;B", ["A&B"], "A&B"), id="ampcontrol-ordinary"),
        pytest.param(
            ("A&bogus;B", "A&amp;bogus;B", ["A&bogus;B"], "A&bogus;B"),
            id="ampcontrol-unknown",
        ),
        pytest.param(
            ("<b>CALLS</b>", "<b>CALLS</b>", ["<b>CALLS</b>"], "<b>CALLS</b>"),
            id="plain-markup",
        ),
        pytest.param(("Σé", "Σé", ["Σé"], "Σé"), id="plain-unicode"),
        pytest.param(('A\\"B', r'A\\"B', ['A\\"B'], 'A\\"B'), id="plain-quote-slash"),
        pytest.param(("A\nB", r"A\nB", ["A", "B"], "A\nB"), id="plain-physical-lf"),
        pytest.param(("A\tB", "A\tB", ["A\tB"], "A B"), id="plain-physical-tab"),
        pytest.param((r"A\nB", r"A\\nB", [r"A\nB"], r"A\nB"), id="plain-literal-n"),
        pytest.param(("A\\", "A\\\\", ["A\\"], "A\\"), id="plain-tail-slash"),
    ]
)
def dot_literal_entity_case(request):
    return request.param


@pytest.fixture(
    params=[
        pytest.param(
            (field, use_clusters, file_output),
            id=field
            + ("-clustered" if use_clusters else "-flat")
            + ("-file" if file_output else "-string"),
        )
        for field in [
            "node_name",
            "node_type",
            "node_path",
            "cluster_label",
            "edge_label",
            "tooltip_key",
            "tooltip_value",
        ]
        for use_clusters in [False, True]
        for file_output in [False, True]
        if field != "cluster_label" or use_clusters
    ]
)
def dot_literal_entity_graph(
    request, dot_literal_entity_case, parsed_same_span, tmp_path
):
    dot = shutil.which("dot")
    if dot is None:
        pytest.skip("Graphviz executable is required for compiled DOT contracts")
    field, use_clusters, file_output = request.param
    caller, protected_json, visible_lines, visible_tooltip = dot_literal_entity_case
    chunks = [c for c in parsed_same_span if c.node_type == "function_definition"]
    assert len(chunks) == 2
    assert [c.metadata["signature"]["name"] for c in chunks] == ["f", "g"]
    assert [(c.start_line, c.end_line) for c in chunks] == [(1, 2), (5, 6)]
    ids = [c.node_id for c in chunks]
    assert len(set(ids)) == 2
    for chunk, name in zip(chunks, ["f", "g"], strict=True):
        chunk.file_path = (
            caller if field in ("node_path", "cluster_label") else "caller.py"
        )
        chunk.metadata.update(
            name=name, chunk_type="function", complexity=7, token_count=0
        )
    if field == "node_name":
        chunks[0].metadata["name"] = caller
    if field == "node_type":
        chunks[0].metadata["chunk_type"] = caller
    relationship = caller if field == "edge_label" else "CALLS"
    properties = {
        caller if field == "tooltip_key" else "note": (
            caller if field == "tooltip_value" else "plain"
        ),
        "other": 0,
    }
    exporter = DotExporter()
    if field == "node_type":
        exporter.set_node_style(
            caller, shape="ellipse", fillcolor="lightblue", style="filled"
        )
    if field == "edge_label":
        exporter.set_edge_style(caller, color="red", style="dotted")
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], relationship, properties)

    def state():
        return [
            [vars(chunk) for chunk in chunks],
            {key: vars(node) for key, node in exporter.nodes.items()},
            [vars(edge) for edge in exporter.edges],
            exporter.graph_attrs,
            exporter.node_attrs,
            exporter.edge_attrs,
            exporter.chunk_type_styles,
            exporter.edge_type_styles,
        ]

    original = copy.deepcopy(state())
    output = exporter.export_string(use_clusters=use_clusters)
    assert output == exporter.export_string(use_clusters=use_clusters)
    path = tmp_path / "literal-entities.dot" if file_output else None
    if path is not None:
        exporter.export(path, use_clusters=use_clusters)
        first = path.read_bytes()
        exporter.export(path, use_clusters=use_clusters)
        assert path.read_bytes() == first
        assert first.replace(b"\r\n", b"\n") == output.encode("utf-8")

    def compile_graph(format_name):
        result = subprocess.run(
            [dot, "-T" + format_name, *([str(path)] if path is not None else [])],
            input=output if path is None else None,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        return result.stdout

    graph = json.loads(compile_graph("json"))
    count = graph.get("_subgraph_cnt", 0)
    assert count == int(use_clusters)
    nodes = graph["objects"][count:]
    assert len(nodes) == 2 and {node["name"] for node in nodes} == set(ids)
    by_name = {node["name"]: node for node in nodes}
    assert all(
        node["shape"] == "ellipse"
        and node["fillcolor"] == "lightblue"
        and node["style"] == "filled"
        for node in nodes
    )
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert (edge["tail"], edge["head"]) == (
        by_name[ids[0]]["_gvid"],
        by_name[ids[1]]["_gvid"],
    )
    assert edge["tail"] != edge["head"]
    assert edge["color"] == "red" and edge["style"] == "dotted"
    if use_clusters:
        cluster = graph["objects"][0]
        assert set(cluster["nodes"]) == {node["_gvid"] for node in nodes}
        assert cluster["style"] == "rounded,filled"
        assert cluster["fillcolor"] == "lightgray" and cluster["color"] == "black"
    assert graph["rankdir"] == "TB"

    svg = ET.fromstring(compile_graph("svg"))
    namespace = "{http://www.w3.org/2000/svg}"
    groups = list(svg.iter(namespace + "g"))
    svg_nodes = [g for g in groups if g.get("class") == "node"]
    assert len(svg_nodes) == 2
    svg_by_id = {g.find(namespace + "title").text: g for g in svg_nodes}
    assert set(svg_by_id) == set(ids)
    assert all(
        t.get("text-anchor") == "middle"
        for group in svg_nodes
        for t in group.iter(namespace + "text")
    )
    svg_edges = [g for g in groups if g.get("class") == "edge"]
    assert len(svg_edges) == 1
    assert svg_edges[0].find(namespace + "title").text == ids[0] + "->" + ids[1]
    anchors = list(svg_edges[0].iter(namespace + "a"))
    assert len(anchors) == 1
    svg_clusters = [g for g in groups if g.get("class") == "cluster"]
    assert len(svg_clusters) == int(use_clusters)
    assert state() == original
    assert set(exporter.nodes) == set(ids)
    assert exporter.get_subgraph_clusters() == {chunks[0].file_path: ids}
    assert (exporter.edges[0].source_id, exporter.edges[0].target_id) == tuple(ids)

    path_lines = (
        visible_lines if field in ("node_path", "cluster_label") else ["caller.py"]
    )
    path_json = (
        protected_json if field in ("node_path", "cluster_label") else "caller.py"
    )
    name_lines = visible_lines if field == "node_name" else ["f"]
    type_lines = visible_lines if field == "node_type" else ["function"]
    first_lines = ("\n".join(name_lines) + " (" + "\n".join(type_lines) + ")").split(
        "\n"
    )
    first_json = (
        (protected_json if field == "node_name" else "f")
        + " ("
        + (protected_json if field == "node_type" else "function")
        + ")"
    )
    node_lines = [
        [
            *(first_lines if index == 0 else ["g (function)"]),
            *path_lines[:-1],
            path_lines[-1] + (":1-2" if index == 0 else ":5-6"),
            "Complexity: 7",
            "Tokens: 0",
        ]
        for index in [0, 1]
    ]
    node_json = [
        r"\n".join(
            [
                first_json if index == 0 else "g (function)",
                path_json + (":1-2" if index == 0 else ":5-6"),
                "Complexity: 7",
                "Tokens: 0",
            ]
        )
        for index in [0, 1]
    ]
    visible = {
        "node": [t.text for t in svg_by_id[ids[0]].iter(namespace + "text")],
        "edge_label": [t.text for t in svg_edges[0].iter(namespace + "text")],
        "tooltip": anchors[0].get("{http://www.w3.org/1999/xlink}title"),
    }
    expected_visible = {
        "node": node_lines[0],
        "edge_label": visible_lines if field == "edge_label" else ["CALLS"],
        "tooltip": (
            (visible_tooltip if field == "tooltip_key" else "note")
            + ": "
            + (visible_tooltip if field == "tooltip_value" else "plain")
            + "; other: 0"
        ),
    }
    compiled = {
        "node": by_name[ids[0]]["label"],
        "edge_label": edge["label"],
        "tooltip": edge["tooltip"],
    }
    expected_compiled = {
        "node": node_json[0],
        "edge_label": protected_json if field == "edge_label" else "CALLS",
        "tooltip": (
            (protected_json if field == "tooltip_key" else "note")
            + ": "
            + (protected_json if field == "tooltip_value" else "plain")
            + "; other: 0"
        ),
    }
    if use_clusters:
        visible["cluster_label"] = [
            t.text for t in svg_clusters[0].iter(namespace + "text")
        ]
        expected_visible["cluster_label"] = path_lines
        compiled["cluster_label"] = graph["objects"][0]["label"]
        expected_compiled["cluster_label"] = path_json
    target = (
        "node"
        if field.startswith("node_")
        else "tooltip" if field.startswith("tooltip_") else field
    )
    return {
        "target": target,
        "visible": visible,
        "expected_visible": expected_visible,
        "compiled": compiled,
        "expected_compiled": expected_compiled,
        "second_visible": [t.text for t in svg_by_id[ids[1]].iter(namespace + "text")],
        "expected_second_visible": node_lines[1],
        "second_json": by_name[ids[1]]["label"],
        "expected_second_json": node_json[1],
    }


def test_dot_literal_entities_visible(dot_literal_entity_graph):
    result = dot_literal_entity_graph
    target = result["target"]
    assert result["visible"][target] == result["expected_visible"][target]
    assert result["visible"] == result["expected_visible"]
    assert result["second_visible"] == result["expected_second_visible"]


def test_dot_literal_entities_json(dot_literal_entity_graph):
    result = dot_literal_entity_graph
    target = result["target"]
    assert result["compiled"][target] == result["expected_compiled"][target]
    assert result["compiled"] == result["expected_compiled"]
    assert result["second_json"] == result["expected_second_json"]


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


@pytest.mark.parametrize("prefix", ["", " ", "\t", "\u2003"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("output_kind", ["string", "file"])
def test_neo4j_csv_retains_boundary_field_whitespace(
    parsed_same_span, prefix, reverse, output_kind, tmp_path
):
    parent, child = parsed_same_span[:2]
    parent.node_id = prefix + "caller-parent"
    child.node_id = prefix + "caller-child"
    value = " property trailing \t\u2003"
    quoted = 'a,b"&<x>中文'
    for chunk in (parent, child):
        chunk.metadata.update({"zz_whitespace": value, "quoted": quoted})
    order = [child, parent] if reverse else [parent, child]
    exporter = Neo4jExporter()
    exporter.add_chunks(order)
    exporter.add_relationship(
        *order, "CALLS", {"zz_whitespace": value, "quoted": quoted}
    )
    exporter.add_relationship(
        *reversed(order), "RETURNS", {"zz_whitespace": value, "quoted": quoted}
    )
    if output_kind == "string":
        nodes_text = exporter.export_string(fmt="csv_nodes")
        edges_text = exporter.export_string(fmt="csv_relationships")
    else:
        exporter.export(tmp_path / "actual", fmt="csv")
        with (tmp_path / "actual_nodes.csv").open(encoding="utf-8", newline="") as f:
            nodes_text = f.read()
        with (tmp_path / "actual_relationships.csv").open(
            encoding="utf-8", newline=""
        ) as f:
            edges_text = f.read()
        command = (tmp_path / "actual_import.sh").read_text(encoding="utf-8")
        assert "--nodes=actual_nodes.csv" in command
        assert "--relationships=actual_relationships.csv" in command
    nodes_reader = csv.DictReader(io.StringIO(nodes_text, newline=""))
    nodes = list(nodes_reader)
    assert nodes_reader.fieldnames[:2] == ["nodeId:ID", ":LABEL"]
    assert len(nodes) == len(exporter.nodes) == 2
    assert {row["nodeId:ID"] for row in nodes} == set(exporter.nodes)
    assert all(row["zz_whitespace"] == value for row in nodes)
    assert all(row["quoted"] == quoted for row in nodes)
    edges_reader = csv.DictReader(io.StringIO(edges_text, newline=""))
    edges = list(edges_reader)
    assert edges_reader.fieldnames[:3] == [":START_ID", ":END_ID", ":TYPE"]
    assert len(edges) == len(exporter.edges) == 2
    assert {(row[":START_ID"], row[":END_ID"], row[":TYPE"]) for row in edges} == {
        (edge.source_id, edge.target_id, edge.relationship_type)
        for edge in exporter.edges
    }
    assert all(row["zz_whitespace"] == value for row in edges)
    assert all(row["quoted"] == quoted for row in edges)


@pytest.mark.parametrize("line_break", ["\n", "\r", "\r\n"], ids=["lf", "cr", "crlf"])
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
@pytest.mark.parametrize("with_edges", [False, True], ids=["no-edges", "edges"])
def test_neo4j_cypher_file_preserves_generated_newlines(
    parsed_same_span, line_break, reverse, with_edges, tmp_path
):
    parent, child = parsed_same_span[:2]
    parent.node_id = "caller" + line_break + "parent"
    child.node_id = "caller" + line_break + "child"
    value = "value" + line_break + "next中文😀"
    for chunk in (parent, child):
        chunk.metadata["zz_multiline"] = value
    order = [child, parent] if reverse else [parent, child]
    exporter = Neo4jExporter()
    exporter.add_chunks(order)
    if with_edges:
        exporter.add_relationship(*order, "CALLS", {"zz_multiline": value})
    generated = exporter.export_string(fmt="cypher")
    for chunk in order:
        assert generated.count(f"nodeId: '{chunk.node_id}'") == (2 if with_edges else 1)
        assert exporter.nodes[chunk.node_id].properties["zz_multiline"] == value
    assert generated.index(f"nodeId: '{order[0].node_id}'") < generated.index(
        f"nodeId: '{order[1].node_id}'"
    )
    assert generated.count(f"zz_multiline: '{value}'") == (3 if with_edges else 2)
    assert ("MATCH (a:CodeChunk" in generated) == with_edges
    assert ("CREATE (a)-[:CALLS" in generated) == with_edges
    assert list(exporter.nodes) == [chunk.node_id for chunk in order]
    if with_edges:
        edge = exporter.edges[0]
        assert (edge.source_id, edge.target_id) == tuple(
            chunk.node_id for chunk in order
        )
    else:
        assert not exporter.edges
    path = tmp_path / "actual.cypher"
    exporter.export(path, fmt="cypher")
    assert path.read_bytes() == generated.encode("utf-8")
    with path.open(encoding="utf-8", newline="") as f:
        assert f.read() == generated
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("line_break", ["\n", "\r", "\r\n"], ids=["lf", "cr", "crlf"])
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
@pytest.mark.parametrize("with_edges", [False, True], ids=["no-edges", "edges"])
def test_neo4j_csv_files_preserve_embedded_newlines(
    parsed_same_span, line_break, reverse, with_edges, tmp_path
):
    parent, child = parsed_same_span[:2]
    parent.node_id = "caller" + line_break + "parent"
    child.node_id = "caller" + line_break + "child"
    value = "value" + line_break + 'next, "quoted"\t\u2003'
    for chunk in (parent, child):
        chunk.metadata["zz_multiline"] = value
    order = [child, parent] if reverse else [parent, child]
    exporter = Neo4jExporter()
    exporter.add_chunks(order)
    if with_edges:
        exporter.add_relationship(*order, "CALLS", {"zz_multiline": value})
        exporter.add_relationship(*reversed(order), "RETURNS", {"zz_multiline": value})
    exporter.export(tmp_path / "multiline", fmt="csv")
    node_ids = {"caller" + line_break + "parent", "caller" + line_break + "child"}
    expected_edges = {
        (order[0].node_id, order[1].node_id, "CALLS"),
        (order[1].node_id, order[0].node_id, "RETURNS"),
    }
    for kind, suffix in [
        ("csv_nodes", "nodes"),
        ("csv_relationships", "relationships"),
    ]:
        generated = exporter.export_string(fmt=kind)
        string_reader = csv.DictReader(io.StringIO(generated, newline=""))
        string_rows = list(string_reader)
        if suffix == "nodes":
            assert string_reader.fieldnames == [
                "nodeId:ID",
                ":LABEL",
                *sorted(
                    {key for node in exporter.nodes.values() for key in node.properties}
                ),
            ]
            assert len(string_rows) == 2
            assert {row["nodeId:ID"] for row in string_rows} == node_ids
        else:
            assert string_reader.fieldnames == [":START_ID", ":END_ID", ":TYPE"] + (
                ["zz_multiline"] if with_edges else []
            )
            assert len(string_rows) == (2 if with_edges else 0)
            assert {
                (row[":START_ID"], row[":END_ID"], row[":TYPE"]) for row in string_rows
            } == (expected_edges if with_edges else set())
        assert all(row["zz_multiline"] == value for row in string_rows)
        path = tmp_path / f"multiline_{suffix}.csv"
        if suffix == "relationships" and not with_edges:
            assert not path.exists()
            continue
        with path.open(encoding="utf-8", newline="") as f:
            file_reader = csv.DictReader(f)
            assert list(file_reader) == string_rows
            assert file_reader.fieldnames == string_reader.fieldnames
        assert path.read_bytes() == generated.encode("utf-8")
    command = (tmp_path / "multiline_import.sh").read_text(encoding="utf-8")
    assert "--nodes=multiline_nodes.csv" in command
    assert ("--relationships=multiline_relationships.csv" in command) == with_edges


@pytest.mark.parametrize("include_nodes", [False, True])
def test_neo4j_csv_empty_relationship_headers_and_files(
    parsed_same_span, include_nodes, tmp_path
):
    exporter = Neo4jExporter()
    chunks = parsed_same_span[:2] if include_nodes else []
    exporter.add_chunks(chunks)
    nodes_reader = csv.DictReader(
        io.StringIO(exporter.export_string(fmt="csv_nodes"), newline="")
    )
    assert {row["nodeId:ID"] for row in nodes_reader} == {
        chunk.node_id for chunk in chunks
    }
    assert nodes_reader.fieldnames[:2] == ["nodeId:ID", ":LABEL"]
    edges_reader = csv.DictReader(
        io.StringIO(exporter.export_string(fmt="csv_relationships"), newline="")
    )
    assert list(edges_reader) == []
    assert edges_reader.fieldnames == [":START_ID", ":END_ID", ":TYPE"]
    exporter.export(tmp_path / "empty_edges", fmt="csv")
    with (tmp_path / "empty_edges_nodes.csv").open(encoding="utf-8", newline="") as f:
        assert {row["nodeId:ID"] for row in csv.DictReader(f)} == {
            chunk.node_id for chunk in chunks
        }
    assert not (tmp_path / "empty_edges_relationships.csv").exists()
    command = (tmp_path / "empty_edges_import.sh").read_text(encoding="utf-8")
    assert "--nodes=empty_edges_nodes.csv" in command
    assert "--relationships=" not in command


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


@pytest.fixture(params=["plain", "yed", "delegated"])
def parsed_xml_graph(request):
    fixture = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    )
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error
    chunks = chunk_file(fixture, "python")
    assert len(chunks) >= 2
    exporter = GraphMLExporter() if request.param == "plain" else GraphMLyEdExporter()
    exporter.add_chunks(chunks[:2])
    exporter.add_relationship(chunks[0], chunks[1], "CALLS")
    options = {"use_yed": False} if request.param == "delegated" else {}
    return exporter, chunks[:2], options


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("codepoint", [0, 8, 11, 31, 0xD800, 0xDFFF, 0xFFFE, 0xFFFF])
@pytest.mark.parametrize(
    "location", ["node_value", "edge_value", "graph", "node_name", "edge_name", "id"]
)
def test_xml_invalid_characters_are_rejected(
    parsed_xml_graph, pretty, codepoint, location
):
    exporter, chunks, options = parsed_xml_graph
    value = f"private-prefix{chr(codepoint)}private-suffix"
    if location == "node_value":
        exporter.nodes[chunks[0].node_id].properties["caller"] = value
    elif location == "edge_value":
        exporter.edges[0].properties["caller"] = value
    elif location == "graph":
        exporter.graph_attrs["id"] = value
    elif location == "node_name":
        exporter.nodes[chunks[0].node_id].properties[value] = "legal"
    elif location == "edge_name":
        exporter.edges[0].properties[value] = "legal"
    else:
        exporter.nodes[value] = exporter.nodes.pop(chunks[0].node_id)
    with pytest.raises(ValueError) as error:
        exporter.export_string(pretty_print=pretty, **options)
    message = str(error.value)
    assert f"U+{codepoint:04X}" in message
    assert "private-prefix" not in message and "private-suffix" not in message
    expected = {
        "node_value": "data.text",
        "edge_value": "data.text",
        "graph": "graph.attribute 'id'",
        "node_name": "key.attribute 'id'",
        "edge_name": "key.attribute 'id'",
        "id": "node.attribute 'id'",
    }
    assert expected[location] in message


@pytest.mark.parametrize("pretty", [False, True])
def test_xml_legal_characters_and_relationships_round_trip(parsed_xml_graph, pretty):
    exporter, chunks, options = parsed_xml_graph
    value = "\t\n\r &<>\"'中文😀 " + "".join(
        chr(cp) for cp in [0x20, 0xD7FF, 0xE000, 0xFFFD, 0x10000, 0x10FFFF]
    )
    exporter.nodes[chunks[0].node_id].properties["caller"] = value
    exporter.edges[0].properties["caller"] = value
    exporter.graph_attrs["caller"] = "中文😀 &<>\"'"
    root = ET.fromstring(exporter.export_string(pretty_print=pretty, **options))
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(f"{ns}graph")
    assert graph is not None
    assert graph.get("caller") == exporter.graph_attrs["caller"]
    assert {node.get("id") for node in graph.findall(f"{ns}node")} == {
        chunk.node_id for chunk in chunks
    }
    edge = graph.find(f"{ns}edge")
    assert edge is not None
    assert (edge.get("source"), edge.get("target")) == tuple(
        chunk.node_id for chunk in chunks
    )
    for key in ["n_caller", "e_caller"]:
        data = graph.find(f".//{ns}data[@key='{key}']")
        assert data is not None
        assert data.text == value.replace("\r", "\n")


def assert_graph_attribute_names_rejected(parsed_xml_graph, attrs, pretty, tmp_path):
    exporter, chunks, options = parsed_xml_graph
    exporter.graph_attrs["caller"] = "legal\t\n\r中文"
    original = dict(exporter.graph_attrs)
    graph_attrs = exporter.graph_attrs
    exporter.graph_attrs.update(attrs)
    rejected_attrs = dict(exporter.graph_attrs)
    nodes, edges = dict(exporter.nodes), list(exporter.edges)
    properties = {key: dict(node.properties) for key, node in nodes.items()}
    existing, absent = tmp_path / "existing.graphml", tmp_path / "absent.graphml"
    sentinel = b"original output\x00\r\n"
    existing.write_bytes(sentinel)
    operations = [
        lambda: exporter.export_string(pretty_print=pretty, **options),
        lambda: exporter.export(existing, pretty_print=pretty, **options),
        lambda: exporter.export(absent, pretty_print=pretty, **options),
    ]
    for operation in operations:
        with pytest.raises(ValueError, match="graph.*attribute") as error:
            operation()
        assert type(error.value) is ValueError
        assert existing.read_bytes() == sentinel
        assert not absent.exists()
        assert exporter.graph_attrs is graph_attrs
        assert exporter.graph_attrs == rejected_attrs
        assert exporter.nodes == nodes and exporter.edges == edges
        assert {key: node.properties for key, node in nodes.items()} == properties
    exporter.graph_attrs.clear()
    exporter.graph_attrs.update(original)
    root, _ = graphml_contract_output(exporter, options, pretty, True, tmp_path)
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(f"{ns}graph")
    assert graph is not None and graph.attrib == original
    assert {node.get("id") for node in graph.findall(f"{ns}node")} == {
        chunk.node_id for chunk in chunks
    }
    edge = graph.find(f"{ns}edge")
    assert (edge.get("source"), edge.get("target")) == tuple(
        chunk.node_id for chunk in chunks
    )


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize(
    "name",
    [
        "",
        "bad attr",
        " caller",
        "caller ",
        "\tcaller",
        "caller\t",
        "\ncaller",
        "caller\n",
        "\rcaller",
        "caller\r",
        "1caller",
        "-caller",
        ".caller",
        "\u0301caller",
        "caller\x00name",
        "caller\x08name",
        "caller<name",
        "caller>name",
        'caller"name',
        "caller'name",
        "caller/name",
        "caller=name",
        "caller&name",
        "a:b:c",
        ":caller",
        "caller:",
        "caller{",
        "caller}",
    ],
)
def test_graph_attribute_names_lexical_rejection(
    parsed_xml_graph, tmp_path, pretty, name
):
    assert_graph_attribute_names_rejected(
        parsed_xml_graph, {name: "legal"}, pretty, tmp_path
    )


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("name", ['a="1" b', 'x="1"></graph><graph y'])
def test_graph_attribute_names_injection(parsed_xml_graph, tmp_path, pretty, name):
    assert_graph_attribute_names_rejected(
        parsed_xml_graph, {name: "legal"}, pretty, tmp_path
    )


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize(
    ("case_name", "attrs"),
    [
        ("unbound", {"unbound:foo": "legal"}),
        ("reserved_xml", {"xmlns:xml": "urn:wrong"}),
        ("reserved_xmlns", {"xmlns:xmlns": "urn:wrong"}),
        ("reserved_uri", {"xmlns:p": "http://www.w3.org/XML/1998/namespace"}),
        ("empty_binding", {"xmlns:p": "", "p:foo": "legal"}),
        (
            "duplicate",
            {
                "xmlns:p": "urn:A",
                "xmlns:q": "urn:A",
                "p:foo": "first",
                "q:foo": "second",
            },
        ),
        ("expanded_xsi", {"{http://www.w3.org/2001/XMLSchema-instance}foo": "legal"}),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_graph_attribute_names_namespace_rejection(
    parsed_xml_graph, tmp_path, pretty, case_name, attrs
):
    assert_graph_attribute_names_rejected(parsed_xml_graph, attrs, pretty, tmp_path)


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("equal_values", [False, True])
@pytest.mark.parametrize("case_name", ["single", "swap", "mask"])
def test_graph_attribute_names_expanded_identity(
    parsed_xml_graph, tmp_path, pretty, equal_values, case_name
):
    attrs = {"{urn:A}foo": "first", "xmlns:ns0": "urn:B"}
    if case_name == "swap":
        attrs["{urn:B}foo"] = "first" if equal_values else "second"
        attrs["xmlns:ns1"] = "urn:A"
    elif case_name == "mask":
        attrs["xmlns:p"] = "urn:A"
        attrs["p:foo"] = "first" if equal_values else "second"
    assert_graph_attribute_names_rejected(parsed_xml_graph, attrs, pretty, tmp_path)


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize(
    "name",
    [
        None,
        1,
        b"caller",
        ET.QName("urn:caller", "name"),
        "caller\ud800",
        "caller\uffff",
        "{urn:\ud800}name",
        "{urn:\x00}name",
        "{urn:A",
        "{}name",
        "{urn:{A}}name",
        "{urn:A}bad:name",
    ],
)
def test_graph_attribute_names_diagnostics(parsed_xml_graph, tmp_path, pretty, name):
    assert_graph_attribute_names_rejected(
        parsed_xml_graph, {name: "legal"}, pretty, tmp_path
    )


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize(
    ("case_name", "attrs", "expected", "namespace"),
    [
        (
            "unicode",
            dict.fromkeys(
                [
                    "description",
                    "_caller",
                    "caller.name",
                    "caller-name",
                    "caller0",
                    "étiquette",
                    "Σ",
                    "中文",
                    "a\u0301",
                ],
                "\t\n\r中文",
            ),
            dict.fromkeys(
                [
                    "description",
                    "_caller",
                    "caller.name",
                    "caller-name",
                    "caller0",
                    "étiquette",
                    "Σ",
                    "中文",
                    "a\u0301",
                ],
                "\t\n\r中文",
            ),
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "xml",
            {"xml:lang": "\t\n\r中文"},
            {"{http://www.w3.org/XML/1998/namespace}lang": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "xsi",
            {"xsi:note": "\t\n\r中文"},
            {"{http://www.w3.org/2001/XMLSchema-instance}note": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "declared",
            {"xmlns:custom": "urn:caller", "custom:name": "\t\n\r中文"},
            {"{urn:caller}name": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "declaration_last",
            {"custom:name": "\t\n\r中文", "xmlns:custom": "urn:caller"},
            {"{urn:caller}name": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "expanded",
            {"{urn:caller}name": "\t\n\r中文"},
            {"{urn:caller}name": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "generated_same",
            {"xmlns:ns0": "urn:caller", "{urn:caller}name": "\t\n\r中文"},
            {"{urn:caller}name": "\t\n\r中文"},
            "http://graphml.graphdrawing.org/xmlns",
        ),
        (
            "default_override",
            {"xmlns": "urn:caller", "description": "\t\n\r中文"},
            {"description": "\t\n\r中文"},
            "urn:caller",
        ),
        (
            "default_undeclared",
            {"xmlns": "", "description": "\t\n\r中文"},
            {"description": "\t\n\r中文"},
            "",
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_graph_attribute_names_supported(
    parsed_xml_graph,
    tmp_path,
    pretty,
    file_output,
    case_name,
    attrs,
    expected,
    namespace,
):
    exporter, chunks, options = parsed_xml_graph
    exporter.graph_attrs.update(attrs)
    before = dict(exporter.graph_attrs)
    root, _ = graphml_contract_output(exporter, options, pretty, file_output, tmp_path)
    ns = f"{{{namespace}}}" if namespace else ""
    graph = root.find(f"{ns}graph")
    assert graph is not None
    assert graph.attrib == {"edgedefault": "directed", "id": "CodeGraph", **expected}
    assert {node.get("id") for node in graph.findall(f"{ns}node")} == {
        chunk.node_id for chunk in chunks
    }
    edge = graph.find(f"{ns}edge")
    assert (edge.get("source"), edge.get("target")) == tuple(
        chunk.node_id for chunk in chunks
    )
    assert exporter.graph_attrs == before


@pytest.mark.parametrize("pretty", [False, True])
def test_graph_attribute_names_yed_binding(parsed_xml_graph, tmp_path, pretty):
    exporter, _, options = parsed_xml_graph
    if isinstance(exporter, GraphMLyEdExporter) and options.get("use_yed", True):
        exporter.graph_attrs["y:foo"] = "\t\n\r中文"
        root, _ = graphml_contract_output(exporter, options, pretty, True, tmp_path)
        graph = root.find("{http://graphml.graphdrawing.org/xmlns}graph")
        assert graph.get("{http://www.yworks.com/xml/graphml}foo") == "\t\n\r中文"
    else:
        assert_graph_attribute_names_rejected(
            parsed_xml_graph, {"y:foo": "legal"}, pretty, tmp_path
        )


@pytest.mark.parametrize("pretty", [False, True])
def test_graph_attribute_names_parser_version(parsed_xml_graph, tmp_path, pretty):
    exporter, _, options = parsed_xml_graph
    name = "\U00010000caller"
    exporter.graph_attrs[name] = "legal"
    try:
        output = exporter.export_string(pretty_print=pretty, **options)
    except ValueError as error:
        assert (
            type(error) is ValueError
            and "graph" in str(error)
            and "attribute" in str(error)
        )
        del exporter.graph_attrs[name]
        assert_graph_attribute_names_rejected(
            parsed_xml_graph, {name: "legal"}, pretty, tmp_path
        )
    else:
        root = ET.fromstring(output)
        graph = root.find("{http://graphml.graphdrawing.org/xmlns}graph")
        assert graph.get(name) == "legal"
        root, _ = graphml_contract_output(exporter, options, pretty, True, tmp_path)
        assert (
            root.find("{http://graphml.graphdrawing.org/xmlns}graph").get(name)
            == "legal"
        )


@pytest.mark.parametrize("pretty", [False, True], ids=["compact", "pretty"])
@pytest.mark.parametrize("file_output", [False, True], ids=["string", "file"])
@pytest.mark.parametrize("separator", ["\t", "\n", "\r"], ids=["tab", "lf", "cr"])
def test_graphml_attribute_whitespace_ids(
    graphml_whitespace_graph, pretty, file_output, separator, tmp_path
):
    exporter, chunks, options, route = graphml_whitespace_graph
    caller_ids = (f"caller{separator}parent", "caller parent")
    original = [(chunk.chunk_id, chunk.content) for chunk in chunks]
    for chunk, caller_id in zip(chunks, caller_ids, strict=True):
        chunk.node_id = caller_id
    exporter.add_chunks(chunks)
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {"note": "forward 中文"})
    exporter.add_relationship(chunks[1], chunks[0], "CALLS", {"note": "reverse 😀"})
    for node in exporter.nodes.values():
        node.properties["caller"] = "ordinary 中文 &<>"
        assert all("\r" not in str(value) for value in node.properties.values())
    root, _ = graphml_contract_output(exporter, options, pretty, file_output, tmp_path)
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(f"{ns}graph")
    assert graph is not None and graph.get("edgedefault") == "directed"
    nodes = graph.findall(f"{ns}node")
    assert len(nodes) == 2
    assert {node.get("id") for node in nodes} == set(caller_ids)
    edges = graph.findall(f"{ns}edge")
    assert len(edges) == 2
    assert {(edge.get("source"), edge.get("target")) for edge in edges} == {
        caller_ids,
        caller_ids[::-1],
    }
    assert {
        (edge.get("source"), edge.find(f"{ns}data[@key='e_note']").text)
        for edge in edges
    } == {(caller_ids[0], "forward 中文"), (caller_ids[1], "reverse 😀")}
    keys = [key.get("id") for key in root.findall(f"{ns}key")]
    assert len(keys) == len(set(keys))
    assert all(data.get("key") in keys for data in root.iter(f"{ns}data"))
    for node in nodes:
        assert node.find(f"{ns}data[@key='node_label']").text == "function_definition"
        assert node.find(f"{ns}data[@key='n_caller']").text == "ordinary 中文 &<>"
        shape = node.find(f"{ns}data/{{http://www.yworks.com/xml/graphml}}ShapeNode")
        assert (shape is not None) == (route == "yed")
    assert [(chunk.chunk_id, chunk.content) for chunk in chunks] == original


@pytest.mark.parametrize("pretty", [False, True], ids=["compact", "pretty"])
@pytest.mark.parametrize("file_output", [False, True], ids=["string", "file"])
@pytest.mark.parametrize("separator", ["\t", "\n", "\r"], ids=["tab", "lf", "cr"])
def test_graphml_attribute_whitespace_graph_keys(
    graphml_whitespace_graph, pretty, file_output, separator, tmp_path
):
    exporter, chunks, options, _ = graphml_whitespace_graph
    caller_key = f"caller{separator}key"
    graph_id = f"graph{separator}中文"
    exporter.graph_attrs["id"] = graph_id
    exporter.add_chunks(chunks)
    for chunk in chunks:
        exporter.nodes[chunk.node_id].properties[caller_key] = "node 中文"
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {caller_key: "edge 😀"})
    root, _ = graphml_contract_output(exporter, options, pretty, file_output, tmp_path)
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(f"{ns}graph")
    assert graph is not None and graph.get("id") == graph_id
    keys = {key.get("id"): key for key in root.findall(f"{ns}key")}
    for prefix, target, expected in [
        ("n", "node", "node 中文"),
        ("e", "edge", "edge 😀"),
    ]:
        key_id = f"{prefix}_{caller_key}"
        assert keys[key_id].get("attr.name") == caller_key
        assert keys[key_id].get("for") == target
        for element in graph.findall(f"{ns}{target}"):
            data = {item.get("key"): item.text for item in element.findall(f"{ns}data")}
            assert data[key_id] == expected
    assert {node.get("id") for node in graph.findall(f"{ns}node")} == {
        chunk.node_id for chunk in chunks
    }
    edge = graph.find(f"{ns}edge")
    assert (edge.get("source"), edge.get("target")) == tuple(
        chunk.node_id for chunk in chunks
    )
    assert all(data.get("key") in keys for data in root.iter(f"{ns}data"))


@pytest.mark.parametrize("pretty", [False, True], ids=["compact", "pretty"])
@pytest.mark.parametrize("file_output", [False, True], ids=["string", "file"])
@pytest.mark.parametrize(
    ("caller", "normalized"),
    [(" \t ", " \t "), ("A\rB", "A\nB"), ("A\nB", "A\nB"), ("A\r\nB", "A\nB")],
    ids=["space-tab", "cr", "lf", "crlf"],
)
def test_graphml_text_normalization(
    graphml_whitespace_graph, pretty, file_output, caller, normalized, tmp_path
):
    exporter, chunks, options, route = graphml_whitespace_graph
    exporter.add_chunks(chunks)
    for chunk in chunks:
        exporter.nodes[chunk.node_id].properties["caller"] = caller
        exporter.nodes[chunk.node_id].properties["name"] = caller
    exporter.add_relationship(chunks[0], chunks[1], caller, {"caller": caller})
    root, output = graphml_contract_output(
        exporter, options, pretty, file_output, tmp_path
    )
    if not file_output:
        if pretty:
            assert "\r" not in output
        elif "\r" in caller:
            assert caller in output
    expected = (
        "A\n\nB"
        if file_output and not pretty and os.name == "nt" and caller == "A\r\nB"
        else normalized
    )
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(f"{ns}graph")
    assert graph is not None
    for node in graph.findall(f"{ns}node"):
        data = {item.get("key"): item.text for item in node.findall(f"{ns}data")}
        assert data["n_caller"] == expected and data["n_name"] == expected
        if route == "yed":
            label = node.find(
                f"{ns}data/{{http://www.yworks.com/xml/graphml}}ShapeNode/{{http://www.yworks.com/xml/graphml}}NodeLabel"
            )
            assert label.text == f"function_definition\\n{expected}"
    edge = graph.find(f"{ns}edge")
    data = {item.get("key"): item.text for item in edge.findall(f"{ns}data")}
    assert data["e_caller"] == expected and data["edge_label"] == expected
    if route == "yed":
        label = edge.find(
            f"{ns}data/{{http://www.yworks.com/xml/graphml}}PolyLineEdge/{{http://www.yworks.com/xml/graphml}}EdgeLabel"
        )
        assert label.text == expected
    assert all(node.properties["caller"] == caller for node in exporter.nodes.values())
    assert exporter.edges[0].relationship_type == caller


@pytest.fixture(params=["plain", "yed", "delegated"])
def graphml_whitespace_graph(request, parsed_same_span):
    chunks = [
        chunk for chunk in parsed_same_span if chunk.node_type == "function_definition"
    ]
    assert [chunk.metadata["signature"]["name"] for chunk in chunks] == ["f", "g"]
    exporter = GraphMLExporter() if request.param == "plain" else GraphMLyEdExporter()
    options = {"use_yed": False} if request.param == "delegated" else {}
    return exporter, chunks, options, request.param


def graphml_contract_output(exporter, options, pretty, file_output, tmp_path):
    output = exporter.export_string(pretty_print=pretty, **options)
    assert output == exporter.export_string(pretty_print=pretty, **options)
    if pretty:
        assert output.splitlines()[0] == '<?xml version="1.0" ?>'
        assert output.endswith("\n")
    else:
        assert not output.startswith("<?xml")
    payload = output
    if file_output:
        path = tmp_path / "caller.graphml"
        exporter.export(path, pretty_print=pretty, **options)
        payload = path.read_bytes()
        assert payload == output.replace("\n", os.linesep).encode("utf-8")
    return ET.fromstring(payload), output


@pytest.mark.parametrize("with_edges", [False, True], ids=["no-edges", "edges"])
@pytest.mark.parametrize(
    "basename",
    [
        "chunks",
        "graph name",
        "graph'quote",
        "graph;printf injected",
        "graph$(printf injected)",
        "graph`printf injected`",
        "graph中文",
    ],
    ids=[
        "ordinary",
        "space",
        "apostrophe",
        "semicolon",
        "dollar",
        "backtick",
        "unicode",
    ],
)
def test_neo4j_import_script_preserves_filename_arguments(
    parsed_same_span, with_edges, basename, tmp_path
):
    parent, child = parsed_same_span[:2]
    exporter = Neo4jExporter()
    exporter.add_chunks([parent, child])
    if with_edges:
        exporter.add_relationship(parent, child, "CALLS")
    exporter.export(tmp_path / basename, fmt="csv")
    nodes = tmp_path / f"{basename}_nodes.csv"
    relationships = tmp_path / f"{basename}_relationships.csv"
    script = tmp_path / f"{basename}_import.sh"
    raw = script.read_bytes()
    assert raw.startswith(b"#!/bin/bash\n")
    assert b"\r" not in raw
    assert nodes.is_file()
    assert relationships.is_file() == with_edges
    assert raw == exporter._generate_import_command(
        nodes, relationships if with_edges else None
    ).encode("utf-8")
    expected = ["import", "--database=neo4j", f"--nodes={basename}_nodes.csv"]
    if with_edges:
        expected.append(f"--relationships={basename}_relationships.csv")
    expected.extend(["--skip-bad-relationships=true", "--skip-duplicate-nodes=true"])
    if os.name == "posix" and (bash := shutil.which("bash")):
        command = tmp_path / "neo4j-admin"
        command.write_text('#!/bin/sh\nprintf "%s\\0" "$@"\n', encoding="utf-8")
        command.chmod(0o700)
        result = subprocess.run(
            [bash, str(script)],
            env={"PATH": str(tmp_path)},
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"".join(
            arg.encode("utf-8") + b"\0" for arg in expected
        )
    tokens = shlex.split(raw.decode("utf-8").replace("\\\n", ""), comments=True)
    assert tokens == ["neo4j-admin", *expected]


@pytest.mark.parametrize("with_edges", [False, True], ids=["no-edges", "edges"])
def test_neo4j_import_script_preserves_lf(parsed_same_span, with_edges, tmp_path):
    parent, child = parsed_same_span[:2]
    exporter = Neo4jExporter()
    exporter.add_chunks([parent, child])
    if with_edges:
        exporter.add_relationship(parent, child, "CALLS")
    exporter.export(tmp_path / "chunks", fmt="csv")
    nodes = tmp_path / "chunks_nodes.csv"
    relationships = tmp_path / "chunks_relationships.csv"
    script = tmp_path / "chunks_import.sh"
    raw = script.read_bytes()
    assert raw.startswith(b"#!/bin/bash\n")
    assert b"\r" not in raw
    assert raw.count(b"\\\n") == (5 if with_edges else 4)
    assert raw == exporter._generate_import_command(
        nodes, relationships if with_edges else None
    ).encode("utf-8")
    assert nodes.exists()
    assert relationships.exists() == with_edges
    expected = ["import", "--database=neo4j", "--nodes=chunks_nodes.csv"]
    if with_edges:
        expected.append("--relationships=chunks_relationships.csv")
    expected.extend(["--skip-bad-relationships=true", "--skip-duplicate-nodes=true"])
    for option in expected[1:]:
        assert option.encode("utf-8") in raw
    assert (b"--relationships=" in raw) == with_edges
    if os.name == "posix":
        assert script.stat().st_mode & 0o100
        bash = shutil.which("bash")
        if bash:
            command = tmp_path / "neo4j-admin"
            command.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
            command.chmod(0o700)
            result = subprocess.run(
                [bash, str(script)],
                env={"PATH": str(tmp_path)},
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout.splitlines() == expected


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize(
    "location", ["node_value", "edge_value", "node_name", "edge_name"]
)
def test_xml_rejected_file_preserves_output_and_registry_recovery(
    parsed_xml_graph, tmp_path, pretty, location
):
    exporter, chunks, options = parsed_xml_graph
    node_attrs, edge_attrs = exporter.node_attrs, exporter.edge_attrs
    node_attrs["custom-node"] = "double"
    edge_attrs["custom-edge"] = "boolean"
    properties = (
        exporter.nodes[chunks[0].node_id].properties
        if location.startswith("node")
        else exporter.edges[0].properties
    )
    key = "caller\x00name" if location.endswith("name") else "caller"
    properties[key] = "legal" if location.endswith("name") else "caller\x00value"
    existing, absent = tmp_path / "existing.graphml", tmp_path / "absent.graphml"
    existing.write_bytes(b"original output")
    before_nodes, before_edges = dict(exporter.nodes), list(exporter.edges)
    for path in [existing, absent]:
        with pytest.raises(ValueError, match="U\\+0000"):
            exporter.export(path, pretty_print=pretty, **options)
    assert existing.read_bytes() == b"original output"
    assert not absent.exists()
    assert exporter.nodes == before_nodes and exporter.edges == before_edges
    del properties[key]
    root = ET.fromstring(exporter.export_string(pretty_print=pretty, **options))
    assert root.tag == "{http://graphml.graphdrawing.org/xmlns}graphml"
    assert exporter.node_attrs is node_attrs and exporter.edge_attrs is edge_attrs
    assert node_attrs["custom-node"] == "double"
    assert edge_attrs["custom-edge"] == "boolean"
    if location == "node_name":
        assert key not in node_attrs
    if location == "edge_name":
        assert key not in edge_attrs


def test_xml_validator_checks_tail_of_real_export(parsed_xml_graph):
    exporter, _, options = parsed_xml_graph
    root = ET.fromstring(exporter.export_string(pretty_print=False, **options))
    graph = root.find("{http://graphml.graphdrawing.org/xmlns}graph")
    assert graph is not None
    graph.tail = "private\x00tail"
    with pytest.raises(ValueError, match="U\\+0000.*graph.tail") as error:
        exporter._validate_xml_characters(root)
    assert "private" not in str(error.value)
    graph.tail = "\t\n\r 中文😀"
    exporter._validate_xml_characters(root)


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_structural_and_caller_label_keys_are_disjoint(
    parsed_xml_graph, pretty, reverse
):
    exporter, chunks, options = parsed_xml_graph
    names = ["label", "node_label", "edge_label", "metadata_label"]
    if reverse:
        names.reverse()
    node_values = {}
    for index, chunk in enumerate(chunks):
        values = {name: f'node-{index} {name} 中文 &<>"' for name in names}
        exporter.nodes[chunk.node_id].properties.update(values)
        node_values[chunk.node_id] = values
    edge_values = {name: f'edge {name} 中文 &<>"' for name in names}
    exporter.edges[0].properties.update(edge_values)
    root = ET.fromstring(exporter.export_string(pretty_print=pretty, **options))
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    keys = root.findall(f"{ns}key")
    key_ids = [key.get("id") for key in keys]
    assert len(key_ids) == len(set(key_ids))
    declarations = {key.get("id"): key.attrib for key in keys}
    assert declarations["node_label"]["for"] == "node"
    assert declarations["edge_label"]["for"] == "edge"
    for domain, prefix in [("node", "n_"), ("edge", "e_")]:
        for name in names:
            declaration = declarations[prefix + name]
            assert declaration["for"] == domain
            assert declaration["attr.name"] == name
            assert declaration["attr.type"] == "string"
    graph = root.find(f"{ns}graph")
    assert graph is not None
    nodes = graph.findall(f"{ns}node")
    edges = graph.findall(f"{ns}edge")
    assert {node.get("id") for node in nodes} == set(node_values)
    assert len(edges) == 1
    for domain, elements in [("node", nodes), ("edge", edges)]:
        for element in elements:
            data = element.findall(f"{ns}data")
            data_keys = [item.get("key") for item in data]
            assert len(data_keys) == len(set(data_keys))
            assert all(declarations[key]["for"] == domain for key in data_keys)
    chunks_by_id = {chunk.node_id: chunk for chunk in chunks}
    for node in nodes:
        chunk = chunks_by_id[node.get("id")]
        data = {item.get("key"): item.text for item in node.findall(f"{ns}data")}
        assert node.get("id") == chunk.node_id
        assert data["node_label"] == chunk.node_type
        assert {name: data["n_" + name] for name in names} == node_values[chunk.node_id]
    edge = edges[0]
    data = {item.get("key"): item.text for item in edge.findall(f"{ns}data")}
    assert data["edge_label"] == "CALLS"
    assert {name: data["e_" + name] for name in names} == edge_values
    assert (edge.get("source"), edge.get("target")) == tuple(
        chunk.node_id for chunk in chunks
    )
