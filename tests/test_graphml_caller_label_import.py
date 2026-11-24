"""NetworkX import keeps structural and caller labels apart (treesitter-chunker#453).

Real parsed chunks are exported through the direct GraphML modules and read
back with the installed ``networkx`` GraphML reader, which maps data by
``attr.name``. The structural label stays under ``label`` and caller metadata
named ``label`` is exposed as ``caller_label``.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chunker import chunk_file, get_parser
from chunker.export.graphml_exporter import GraphMLExporter
from chunker.export.graphml_yed_exporter import GraphMLyEdExporter

nx = pytest.importorskip("networkx")

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)
GRAPHML = "{http://graphml.graphdrawing.org/xmlns}"
NODE_CALLER = {
    "label": 'caller node 中文 &<>"',
    "caller_label": "already namespaced node",
    "caller_caller_label": "twice namespaced node",
    "metadata_label": "ordinary node metadata",
}
EDGE_CALLER = {
    "label": "caller edge 中文",
    "caller_label": "already namespaced edge",
}
# Independent oracle for the declared ``attr.name`` of each caller key.
DECLARED = {
    "label": "caller_label",
    "caller_label": "caller_caller_label",
    "caller_caller_label": "caller_caller_caller_label",
    "metadata_label": "metadata_label",
}
ROUTES = {
    "plain": (GraphMLExporter, {}),
    "yed": (GraphMLyEdExporter, {}),
    "delegated": (GraphMLyEdExporter, {"use_yed": False}),
}


def _graph(route: str):
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    chunks = chunk_file(FIXTURE, "python")
    assert len(chunks) >= 2
    chunks = chunks[:2]
    exporter_class, options = ROUTES[route]
    exporter = exporter_class()
    exporter.add_chunks(chunks)
    for chunk in chunks:
        exporter.nodes[chunk.node_id].properties.update(NODE_CALLER)
    exporter.add_relationship(chunks[0], chunks[1], "CALLS", dict(EDGE_CALLER))
    return exporter, chunks, options


def _import(exporter, options, pretty: bool, output: str, tmp_path: Path):
    if output == "string":
        return nx.parse_graphml(exporter.export_string(pretty_print=pretty, **options))
    path = tmp_path / "graph.graphml"
    exporter.export(path, pretty_print=pretty, **options)
    return nx.read_graphml(path)


@pytest.mark.parametrize("output", ["string", "file"])
@pytest.mark.parametrize("pretty", [False, True])
@pytest.mark.parametrize("route", ["plain", "delegated"])
def test_networkx_import_exposes_structural_and_caller_labels(
    route, pretty, output, tmp_path
):
    exporter, chunks, options = _graph(route)
    graph = _import(exporter, options, pretty, output, tmp_path)
    assert set(graph.nodes) == {chunk.node_id for chunk in chunks}
    for chunk in chunks:
        data = graph.nodes[chunk.node_id]
        assert data["label"] == chunk.node_type
        assert {name: data[DECLARED[name]] for name in NODE_CALLER} == NODE_CALLER
    assert list(graph.edges) == [(chunks[0].node_id, chunks[1].node_id)]
    edge = graph.edges[chunks[0].node_id, chunks[1].node_id]
    assert edge["label"] == "CALLS"
    assert {name: edge[DECLARED[name]] for name in EDGE_CALLER} == EDGE_CALLER


@pytest.mark.parametrize("output", ["string", "file"])
@pytest.mark.parametrize("pretty", [False, True])
def test_networkx_yed_import_keeps_caller_label_beside_graphics(
    pretty, output, tmp_path
):
    exporter, chunks, options = _graph("yed")
    # The fixture has no top-level name property. Add one to its class only.
    class_chunk, function_chunk = chunks
    exporter.nodes[class_chunk.node_id].properties["name"] = "Renderer\r\nDisplay"
    expected = {
        class_chunk.node_id: "class_definition\nRenderer\nDisplay",
        function_chunk.node_id: "function_definition",
    }
    if output == "string":
        xml = exporter.export_string(pretty_print=pretty, **options)
        root = ET.fromstring(xml)
        graph = nx.parse_graphml(xml)
    else:
        path = tmp_path / "graph.graphml"
        exporter.export(path, pretty_print=pretty, **options)
        root = ET.parse(path).getroot()
        graph = nx.read_graphml(path)
    yed = "{http://www.yworks.com/xml/graphml}"
    assert {
        node.attrib["id"]: node.findtext(f"{GRAPHML}data/{yed}ShapeNode/{yed}NodeLabel")
        for node in root.iter(f"{GRAPHML}node")
    } == expected
    for chunk in chunks:
        data = graph.nodes[chunk.node_id]
        assert data["label"] == expected[chunk.node_id]
        assert {name: data[DECLARED[name]] for name in NODE_CALLER} == NODE_CALLER
    edge = graph.edges[chunks[0].node_id, chunks[1].node_id]
    assert edge["label"] == "CALLS"
    assert {name: edge[DECLARED[name]] for name in EDGE_CALLER} == EDGE_CALLER


def test_yed_renders_non_string_chunk_names():
    np = pytest.importorskip("numpy")
    class_chunk, function_chunk = chunk_file(FIXTURE, "python")[:2]
    class_chunk.metadata["name"] = np.array(["Renderer", "Display"])
    function_chunk.metadata["name"] = 0
    exporter = GraphMLyEdExporter()
    exporter.add_chunks([class_chunk, function_chunk])

    xml = exporter.export_string(pretty_print=False)
    graph = nx.parse_graphml(xml)
    assert (
        graph.nodes[class_chunk.node_id]["label"]
        == "class_definition\n['Renderer' 'Display']"
    )
    assert graph.nodes[function_chunk.node_id]["label"] == "function_definition\n0"


@pytest.mark.parametrize("route", ["plain", "yed", "delegated"])
def test_key_ids_stay_and_declared_names_are_unique(route):
    exporter, _, options = _graph(route)
    root = ET.fromstring(exporter.export_string(pretty_print=False, **options))
    declarations = {key.get("id"): key.attrib for key in root.findall(f"{GRAPHML}key")}
    assert declarations["node_label"]["attr.name"] == "label"
    assert declarations["edge_label"]["attr.name"] == "label"
    for prefix, domain, caller in [
        ("n_", "node", NODE_CALLER),
        ("e_", "edge", EDGE_CALLER),
    ]:
        for name in caller:
            assert declarations[prefix + name]["for"] == domain
            assert declarations[prefix + name]["attr.name"] == DECLARED[name]
        names = [
            item.get("attr.name")
            for item in declarations.values()
            if item.get("for") == domain and "attr.name" in item
        ]
        assert len(names) == len(set(names))
