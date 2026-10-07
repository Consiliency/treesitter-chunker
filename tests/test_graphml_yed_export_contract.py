"""Real-chunk contracts for the yEd GraphML export path."""

import xml.etree.ElementTree as ET
from pathlib import Path

from chunker import chunk_file
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
