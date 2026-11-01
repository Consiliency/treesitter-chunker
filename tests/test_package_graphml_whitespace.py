"""Package GraphML exporter whitespace contracts (treesitter-chunker#489).

These tests cover the package-level ``chunker.export.GraphMLExporter``
(``chunker/export/formats/graph.py``), which takes chunks and relationships
directly. The direct graph-model modules have their own contracts in
``tests/test_graphml_exporter.py``.
"""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.parsers import expat

import networkx as nx
import pytest

from chunker import chunk_file, get_parser
from chunker.export import GraphMLExporter
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    ExportMetadata,
    RelationshipType,
)

NS = "{http://graphml.graphdrawing.org/xmlns}"
FIXTURE = Path(__file__).parent / "fixtures" / "graph_same_span.py"
ROUTES = ["stringio", "text-stream", "path", "str-path"]


@pytest.fixture
def parsed_functions():
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    chunks = [
        chunk
        for chunk in chunk_file(FIXTURE, "python")
        if chunk.node_type == "function_definition"
    ]
    assert [chunk.metadata["signature"]["name"] for chunk in chunks] == ["f", "g"]
    return chunks


def export_graphml(exporter, chunks, relationships, route, tmp_path, metadata=None):
    """Export through one package route; return the parsed root, text and path."""
    path = None
    if route == "stringio":
        stream = io.StringIO()
        exporter.export(chunks, relationships, stream, metadata)
        text = stream.getvalue()
        root = ET.fromstring(text)
    elif route == "text-stream":
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="utf-8")
        exporter.export(chunks, relationships, stream, metadata)
        stream.flush()
        payload = buffer.getvalue()
        text = payload.decode("utf-8")
        root = ET.fromstring(payload)
    else:
        path = tmp_path / "package.graphml"
        exporter.export(
            chunks,
            relationships,
            path if route == "path" else str(path),
            metadata,
        )
        payload = path.read_bytes()
        text = payload.decode("utf-8")
        root = ET.fromstring(payload)
    return root, text, path


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("separator", ["\t", "\n", "\r"], ids=["tab", "lf", "cr"])
def test_package_graphml_whitespace_ids(parsed_functions, route, separator, tmp_path):
    caller_ids = (f"caller{separator}中文", "caller 中文")
    for chunk, caller_id in zip(parsed_functions, caller_ids, strict=True):
        chunk.chunk_id = caller_id
    relationships = [
        ChunkRelationship(
            caller_ids[0], caller_ids[1], RelationshipType.CALLS, {"note": "forward"}
        ),
        ChunkRelationship(
            caller_ids[1], caller_ids[0], RelationshipType.USES, {"note": "reverse"}
        ),
    ]
    exporter = GraphMLExporter()
    exporter.set_edge_attributes(["relationship_type", "note"])
    root, _, path = export_graphml(
        exporter, parsed_functions, relationships, route, tmp_path
    )

    graph = root.find(f"{NS}graph")
    assert graph is not None and graph.get("edgedefault") == "directed"
    nodes = graph.findall(f"{NS}node")
    assert [node.get("id") for node in nodes] == list(caller_ids)
    keys = {key.get("id"): key.get("attr.name") for key in root.findall(f"{NS}key")}
    for node, chunk in zip(nodes, parsed_functions, strict=True):
        data = {keys[item.get("key")]: item.text for item in node.findall(f"{NS}data")}
        assert data == {
            "node_type": "function_definition",
            "language": "python",
            "file_path": chunk.file_path,
            "start_line": str(chunk.start_line),
            "end_line": str(chunk.end_line),
        }
    edges = graph.findall(f"{NS}edge")
    observed = []
    for edge in edges:
        data = {keys[item.get("key")]: item.text for item in edge.findall(f"{NS}data")}
        observed.append((edge.get("source"), edge.get("target"), data))
    assert observed == [
        (
            caller_ids[0],
            caller_ids[1],
            {"relationship_type": "calls", "note": "forward"},
        ),
        (
            caller_ids[1],
            caller_ids[0],
            {"relationship_type": "uses", "note": "reverse"},
        ),
    ]
    assert [chunk.chunk_id for chunk in parsed_functions] == list(caller_ids)

    if path is not None:
        imported = nx.read_graphml(path)
        assert imported.is_directed()
        assert set(imported.nodes) == set(caller_ids)
        assert set(imported.edges) == {caller_ids, caller_ids[::-1]}
        assert imported.nodes[caller_ids[0]]["node_type"] == "function_definition"
        assert imported.edges[caller_ids]["note"] == "forward"


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    ("caller", "decoded"),
    [
        (" \t ", " \t "),
        ("A\rB", "A\nB"),
        ("A\nB", "A\nB"),
        ("A\r\nB", "A\nB"),
        ("中文 &<>\"'", "中文 &<>\"'"),
    ],
    ids=["space-tab", "cr", "lf", "crlf", "unicode-markup"],
)
def test_package_graphml_declaration_and_text_contracts(
    parsed_functions, route, caller, decoded, tmp_path
):
    for chunk in parsed_functions:
        chunk.parent_context = caller
    relationships = [
        ChunkRelationship(
            parsed_functions[0].chunk_id,
            parsed_functions[1].chunk_id,
            RelationshipType.CALLS,
            {"note": caller},
        )
    ]
    metadata = ExportMetadata(
        fmt=ExportFormat.GRAPHML,
        version="1.0",
        created_at=f"2026-10-31{caller}00:00:00Z",
        source_files=[str(FIXTURE)],
        chunk_count=len(parsed_functions),
        relationship_count=len(relationships),
        options={},
    )
    exporter = GraphMLExporter()
    exporter.set_edge_attributes(["relationship_type", "note"])
    root, text, _ = export_graphml(
        exporter, parsed_functions, relationships, route, tmp_path, metadata
    )

    reference = io.StringIO()
    exporter.export(parsed_functions, relationships, reference, metadata)
    reference = reference.getvalue()
    assert reference.splitlines()[0] == '<?xml version="1.0" ?>'
    assert reference.endswith("\n")
    assert "\r" not in reference
    # The metadata comment carries the caller text too: CR and CRLF become LF.
    comment = f"<!--Generated by TreeSitter Chunker - 2026-10-31{decoded}00:00:00Z-->"
    assert comment in reference
    native = reference if route == "stringio" else reference.replace("\n", os.linesep)
    assert text == native
    assert root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation") == (
        "http://graphml.graphdrawing.org/xmlns "
        "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
    )
    keys = {key.get("id"): key.get("attr.name") for key in root.findall(f"{NS}key")}
    assert list(keys.values()) == [
        "node_type",
        "language",
        "file_path",
        "start_line",
        "end_line",
        "parent_context",
        "relationship_type",
        "note",
    ]
    graph = root.find(f"{NS}graph")
    for node in graph.findall(f"{NS}node"):
        data = {keys[item.get("key")]: item.text for item in node.findall(f"{NS}data")}
        assert data["parent_context"] == decoded
    edge = graph.find(f"{NS}edge")
    data = {keys[item.get("key")]: item.text for item in edge.findall(f"{NS}data")}
    assert data == {"relationship_type": "calls", "note": decoded}
    assert all(chunk.parent_context == caller for chunk in parsed_functions)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("parent_context", "a\x00b", expat.ExpatError),
        ("parent_context", "a\ufffeb", expat.ExpatError),
        ("chunk_id", "a\x01b", expat.ExpatError),
        ("parent_context", "a\ud800b", UnicodeEncodeError),
    ],
    ids=["nul-text", "fffe-text", "control-id", "surrogate-text"],
)
def test_package_graphml_rejects_malformed_xml_before_writing(
    parsed_functions, route, field, value, error, tmp_path
):
    setattr(parsed_functions[0], field, value)
    exporter = GraphMLExporter()
    if route in {"stringio", "text-stream"}:
        buffer = io.BytesIO()
        stream = (
            io.StringIO()
            if route == "stringio"
            else io.TextIOWrapper(buffer, encoding="utf-8")
        )
        with pytest.raises(error):
            exporter.export(parsed_functions, [], stream)
        stream.flush()
        written = stream.getvalue() if route == "stringio" else buffer.getvalue()
        assert not written
    else:
        path = tmp_path / "rejected.graphml"
        with pytest.raises(error):
            exporter.export(
                parsed_functions, [], path if route == "path" else str(path)
            )
        assert not path.exists()
