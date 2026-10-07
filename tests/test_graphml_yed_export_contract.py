"""Real-chunk contracts for the yEd GraphML export path."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chunker import chunk_file, get_parser
from chunker.export.graphml_yed_exporter import GraphMLyEdExporter


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)
GRAPHML = "{http://graphml.graphdrawing.org/xmlns}"
YED = "{http://www.yworks.com/xml/graphml}"


def test_yed_export_keeps_unique_nodes_edges_and_direction() -> None:
    chunks = chunk_file(FIXTURE, "python")
    assert len(chunks) >= 2
    exporter = GraphMLyEdExporter()
    exporter.add_chunks(chunks[:2])
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {"line": 5})

    root = ET.fromstring(exporter.export_string(pretty_print=False))
    graph = root.find(f"{GRAPHML}graph")
    assert graph is not None
    nodes = graph.findall(f"{GRAPHML}node")
    edges = graph.findall(f"{GRAPHML}edge")
    expected_ids = {chunk.node_id for chunk in chunks[:2]}
    assert len(nodes) == len(expected_ids) == 2
    assert {node.get("id") for node in nodes} == expected_ids
    assert len(edges) == 1
    edge = edges[0]
    assert edge.get("id") == "e0"
    assert edge.get("source") == chunks[0].node_id
    assert edge.get("target") == chunks[1].node_id
    assert all(node.find(f"{GRAPHML}data/{YED}ShapeNode") is not None for node in nodes)
    assert edge.find(f"{GRAPHML}data/{YED}PolyLineEdge") is not None

    plain = ET.fromstring(exporter.export_string(pretty_print=False, use_yed=False))
    plain_graph = plain.find(f"{GRAPHML}graph")
    assert plain_graph is not None
    assert len(plain_graph.findall(f"{GRAPHML}node")) == 2
    assert len(plain_graph.findall(f"{GRAPHML}edge")) == 1


@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("use_yed", [False, True])
def test_yed_caller_labels_remain_distinct_from_structural_graphics(pretty, use_yed):
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    chunks = chunk_file(FIXTURE, "python")
    assert len(chunks) >= 2
    exporter = GraphMLyEdExporter()
    exporter.add_chunks(chunks[:2])
    for chunk in chunks[:2]:
        exporter.nodes[chunk.node_id].properties["label"] = "caller node 中文 &<>"
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", {"label": "caller edge"})
    root = ET.fromstring(exporter.export_string(pretty_print=pretty, use_yed=use_yed))
    keys = [key.get("id") for key in root.findall(f"{GRAPHML}key")]
    assert len(keys) == len(set(keys))
    graph = root.find(f"{GRAPHML}graph")
    assert graph is not None
    nodes = graph.findall(f"{GRAPHML}node")
    assert {node.get("id") for node in nodes} == {chunk.node_id for chunk in chunks[:2]}
    chunks_by_id = {chunk.node_id: chunk for chunk in chunks[:2]}
    for node in nodes:
        chunk = chunks_by_id[node.get("id")]
        data = {item.get("key"): item.text for item in node.findall(f"{GRAPHML}data")}
        assert data["node_label"] == chunk.node_type
        assert data["n_label"] == "caller node 中文 &<>"
        shape = node.find(f"{GRAPHML}data/{YED}ShapeNode")
        if use_yed:
            assert shape is not None
            label = shape.find(f"{YED}NodeLabel")
            assert label is not None and label.text is not None
            assert label.text.startswith(chunk.node_type)
        else:
            assert shape is None
    edge = graph.find(f"{GRAPHML}edge")
    assert edge is not None
    data = {item.get("key"): item.text for item in edge.findall(f"{GRAPHML}data")}
    assert data["edge_label"] == "CALLS" and data["e_label"] == "caller edge"
    graphics = edge.find(f"{GRAPHML}data/{YED}PolyLineEdge")
    if use_yed:
        assert graphics is not None
        label = graphics.find(f"{YED}EdgeLabel")
        assert label is not None and label.text == "CALLS"
    else:
        assert graphics is None
    assert (edge.get("source"), edge.get("target")) == (
        chunks[0].node_id,
        chunks[1].node_id,
    )


@pytest.mark.parametrize("pretty", [False, True])
def test_yed_graphics_are_validated_and_recover(pretty):
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    chunks = chunk_file(FIXTURE, "python")
    assert len(chunks) >= 2
    exporter = GraphMLyEdExporter()
    exporter.add_chunks(chunks[:2])
    exporter.add_relationship(chunks[0], chunks[1], "CALLS")
    style = exporter.default_edge_styles["CALLS"]
    original = style["color"]
    style["color"] = "private\x00color"
    with pytest.raises(ValueError, match="U\\+0000.*y:LineStyle.attribute 'color'"):
        exporter.export_string(pretty_print=pretty)
    style["color"] = original
    root = ET.fromstring(exporter.export_string(pretty_print=pretty))
    graph = root.find(f"{GRAPHML}graph")
    assert graph is not None
    assert all(
        node.find(f"{GRAPHML}data/{YED}ShapeNode") is not None
        for node in graph.findall(f"{GRAPHML}node")
    )
    edge = graph.find(f"{GRAPHML}edge")
    assert edge is not None
    assert edge.find(f"{GRAPHML}data/{YED}PolyLineEdge") is not None
    assert edge.get("source") == chunks[0].node_id
    assert edge.get("target") == chunks[1].node_id
