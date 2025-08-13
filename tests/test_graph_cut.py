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
