import pytest

from chunker.graph.cut import graph_cut


def test_graph_cut_radius_budget_and_weights():
    nodes = [
        {"id": "A", "attrs": {}},
        {"id": "B", "attrs": {}},
        {"id": "C", "attrs": {"change_freq": 10}},
        {"id": "D", "attrs": {}},
    ]
    edges = [
        {"src": "A", "dst": "B", "type": "DEFINES", "weight": 1},
        {"src": "B", "dst": "C", "type": "CALLS", "weight": 1},
        {"src": "C", "dst": "D", "type": "REFERENCES", "weight": 1},
    ]

    # Radius 1 from A should include A and B; budget 2 keeps to 2 nodes
    selected, induced = graph_cut(["A"], nodes, edges, radius=1, budget=2)
    assert set(selected) <= {"A", "B"}
    # With larger radius and budget, C should appear; C has hotspot weight
    selected2, _ = graph_cut(["A"], nodes, edges, radius=3, budget=4)
    assert {"A", "B", "C"}.issubset(set(selected2))


@pytest.mark.parametrize(
    ("source_key", "target_key"),
    [
        ("src", "dst"),
        ("source_id", "target_id"),
        ("src", "target_id"),
        ("source_id", "dst"),
    ],
)
def test_graph_cut_preserves_edges_between_selected_nodes(source_key, target_key):
    nodes = [{"id": node_id} for node_id in ("A", "B", "C")]
    forward = {source_key: "A", target_key: "B", "type": "CALLS"}
    outgoing = {source_key: "B", target_key: "C", "type": "CALLS"}
    incoming = {source_key: "C", target_key: "A", "type": "CALLS"}
    back = {source_key: "B", target_key: "A", "type": "REFERENCES"}

    edges = [forward, outgoing, incoming, back]
    selected, induced = graph_cut(["A"], nodes, edges, radius=1)

    assert set(selected) == {"A", "B"}
    assert induced == [forward, back]
    assert induced[0] is forward
    assert induced[1] is back


def test_graph_cut_prefers_nonempty_canonical_endpoints():
    nodes = [{"id": node_id} for node_id in ("A", "B", "C")]
    canonical = {"src": "A", "dst": "B", "source_id": "C", "target_id": "C"}
    fallback = {"src": "", "dst": "", "source_id": "B", "target_id": "A"}

    selected, induced = graph_cut(["A"], nodes, [canonical, fallback], radius=1)

    assert set(selected) == {"A", "B"}
    assert induced == [canonical, fallback]
