"""SCALE SL-4: determinism guarantees for clustering, graph-cut, and xref.

These tests pin down the reproducibility fixes for the deterministic
clustering/graph + index-based xref lane:

* ``ClusteringEngine`` seeds the Leiden optimiser so repeated runs give
  identical clusters.
* ``graph_cut`` breaks score ties on the node id (ascending) so truncation to
  ``budget`` is reproducible regardless of set iteration order.
* ``build_xref`` resolves references via name/export indexes (not an all-pairs
  scan), keys every edge on the frozen IF-0-IDENTITY-1 ``node_id``, and
  de-duplicates edges.

They are written to FAIL on the pre-fix code (no ``seed`` kwarg; set-order tie
breaking; duplicate un-deduped edges) and pass after the fix.
"""

from __future__ import annotations

import pytest

from chunker.graph.cut import graph_cut
from chunker.graph.xref import build_xref
from chunker.types import CodeChunk


# ---------------------------------------------------------------------------
# (a) Leiden clustering is deterministic when seeded
# ---------------------------------------------------------------------------
def _make_community_graph() -> tuple[dict[str, dict], list[dict]]:
    """Two dense communities weakly linked -> a non-trivial partition."""
    symbols: dict[str, dict] = {}
    for group in ("a", "b"):
        for i in range(6):
            sid = f"mod_{group}:{group}{i}"
            symbols[sid] = {
                "name": f"{group}{i}",
                "kind": "function",
                "file": f"{group}.py",
                "module": f"mod_{group}",
            }

    relationships: list[dict] = []
    # Dense intra-community links.
    for group in ("a", "b"):
        members = [f"mod_{group}:{group}{i}" for i in range(6)]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                relationships.append(
                    {"from": members[i], "to": members[j], "type": "calls"}
                )
    # A single weak inter-community link.
    relationships.append({"from": "mod_a:a0", "to": "mod_b:b0", "type": "calls"})
    return symbols, relationships


def test_leiden_clustering_is_deterministic_when_seeded():
    pytest.importorskip("leidenalg")
    pytest.importorskip("igraph")
    from chunker.clustering.engine import ClusteringEngine

    symbols, relationships = _make_community_graph()

    # Must accept an explicit seed (fails on pre-fix code: no such kwarg).
    results = []
    for _ in range(3):
        engine = ClusteringEngine(seed=42)
        res = engine.cluster(symbols, relationships)
        # timestamp lives under metadata and legitimately varies; compare the
        # deterministic parts of the result only.
        results.append((res["hierarchy"], res["metrics"]))

    first = results[0]
    for other in results[1:]:
        assert other == first, "seeded Leiden clustering must be reproducible"


def test_leiden_different_seed_still_reproducible():
    """A different fixed seed is itself reproducible run-to-run."""
    pytest.importorskip("leidenalg")
    pytest.importorskip("igraph")
    from chunker.clustering.engine import ClusteringEngine

    symbols, relationships = _make_community_graph()

    r1 = ClusteringEngine(seed=7).cluster(symbols, relationships)
    r2 = ClusteringEngine(seed=7).cluster(symbols, relationships)
    assert r1["hierarchy"] == r2["hierarchy"]
    assert r1["metrics"] == r2["metrics"]


# ---------------------------------------------------------------------------
# (b) graph_cut tie-order is deterministic (stable-id tie break)
# ---------------------------------------------------------------------------
def test_graph_cut_tie_order_is_deterministic():
    # Twenty isolated seed nodes: identical distance (0), zero out-degree, no
    # change_freq -> identical score. Only the tie-break decides which survive
    # truncation to `budget`. Deliberately feed ids in a non-sorted order so a
    # set-iteration-order implementation cannot accidentally match.
    ids = [f"n{i:02d}" for i in range(20)]
    shuffled = ids[10:] + ids[:10]
    nodes = [{"id": nid, "attrs": {}} for nid in shuffled]
    edges: list[dict] = []
    budget = 10

    selected, induced = graph_cut(
        shuffled, nodes, edges, radius=2, budget=budget
    )

    # With ties broken on ascending id, the surviving `budget` nodes must be
    # the lexicographically smallest ids, in ascending order.
    expected = sorted(ids)[:budget]
    assert selected == expected
    assert induced == []

    # And it must be identical across repeated invocations.
    selected2, _ = graph_cut(shuffled, nodes, edges, radius=2, budget=budget)
    assert selected2 == selected


# ---------------------------------------------------------------------------
# (c) build_xref: index-based, node_id-keyed, de-duplicated
# ---------------------------------------------------------------------------
def _make_chunk(
    node_type: str,
    name: str,
    byte_start: int,
    *,
    imports: list[str] | None = None,
    calls: list[str] | None = None,
    inherits: list[str] | None = None,
    references: list[str] | None = None,
) -> CodeChunk:
    md: dict = {"signature": {"name": name}}
    if imports:
        md["imports"] = imports
    if calls:
        md["calls"] = calls
    if inherits:
        md["inherits"] = inherits
    if references:
        md["references"] = references
    # Distinct byte_start + content -> distinct node_id per chunk (otherwise
    # every chunk in the same file with empty route collides on node_id).
    return CodeChunk(
        language="python",
        file_path="/tmp/x.py",
        node_type=node_type,
        start_line=byte_start,
        end_line=byte_start + 2,
        byte_start=byte_start,
        byte_end=byte_start + 10,
        parent_context="module",
        content=f"def {name}():\n  pass  # @{byte_start}\n",
        qualified_route=[f"{node_type}:{name}"],
        metadata=md,
    )


def test_xref_is_node_id_keyed_and_resolves_multi_chunk():
    parent = _make_chunk("class_definition", "Base", 0)
    child = _make_chunk("method_definition", "foo", 20)
    child.parent_chunk_id = parent.node_id

    imported = _make_chunk("function_definition", "util", 40)
    importer = _make_chunk("function_definition", "caller", 60, imports=["util"])

    callee = _make_chunk("function_definition", "g", 80)
    caller = _make_chunk("function_definition", "f", 100, calls=["g"])

    derived = _make_chunk("class_definition", "Child", 120, inherits=["Base"])

    ref_target = _make_chunk("function_definition", "h", 140)
    referrer = _make_chunk("function_definition", "ref", 160, references=["h"])

    chunks = [
        parent,
        child,
        imported,
        importer,
        callee,
        caller,
        derived,
        ref_target,
        referrer,
    ]
    # Sanity: node_ids are genuinely distinct so keying is meaningful.
    node_ids = {c.node_id for c in chunks}
    assert len(node_ids) == len(chunks)

    nodes, edges = build_xref(chunks)

    # Every node is keyed on node_id.
    assert {n["id"] for n in nodes} == node_ids
    # Every edge endpoint is a node_id (IF-0-IDENTITY-1 keying preserved).
    for e in edges:
        assert e["src"] in node_ids
        assert e["dst"] in node_ids

    def has_edge(src: str, dst: str, typ: str) -> bool:
        return any(
            e["src"] == src and e["dst"] == dst and e["type"] == typ for e in edges
        )

    assert has_edge(parent.node_id, child.node_id, "DEFINES")
    assert has_edge(importer.node_id, imported.node_id, "IMPORTS")
    assert has_edge(caller.node_id, callee.node_id, "CALLS")
    assert has_edge(derived.node_id, parent.node_id, "INHERITS")
    assert has_edge(referrer.node_id, ref_target.node_id, "REFERENCES")

    # REFERENCES weight preserved at 0.5.
    ref_edges = [e for e in edges if e["type"] == "REFERENCES"]
    assert ref_edges and all(e["weight"] == 0.5 for e in ref_edges)


def test_xref_dedups_edges():
    # A duplicate import name would, under the old code, emit two identical
    # IMPORTS edges. The index-based build de-duplicates them.
    imported = _make_chunk("function_definition", "util", 0)
    importer = _make_chunk(
        "function_definition", "caller", 20, imports=["util", "util"]
    )

    _nodes, edges = build_xref([imported, importer])

    imports_edges = [
        e
        for e in edges
        if e["type"] == "IMPORTS"
        and e["src"] == importer.node_id
        and e["dst"] == imported.node_id
    ]
    assert len(imports_edges) == 1, "duplicate edges must be de-duplicated"


def test_xref_reference_edge_order_is_deterministic():
    # Multiple references resolve to distinct targets; edge emission order must
    # be stable (references are sorted before resolution) across builds.
    targets = [
        _make_chunk("function_definition", name, 20 + i * 20)
        for i, name in enumerate(["zeta", "alpha", "mu"])
    ]
    referrer = _make_chunk(
        "function_definition",
        "ref",
        0,
        references=["zeta", "alpha", "mu"],
    )
    chunks = [referrer, *targets]

    _n1, e1 = build_xref(chunks)
    _n2, e2 = build_xref(chunks)
    assert e1 == e2

    ref_dsts = [e["dst"] for e in e1 if e["type"] == "REFERENCES"]
    by_name = {t.metadata["signature"]["name"]: t.node_id for t in targets}
    # Sorted reference names -> alpha, mu, zeta.
    assert ref_dsts == [by_name["alpha"], by_name["mu"], by_name["zeta"]]
