from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str, str] | None:
    src = edge.get("src") or edge.get("source_id")
    dst = edge.get("dst") or edge.get("target_id")
    return (src, dst) if src and dst else None


def graph_cut(
    seeds: Iterable[str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    radius: int = 2,
    budget: int = 200,
    weights: dict[str, float] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Compute a minimal subgraph around seeds bounded by radius and budget.

    Edges may use src/dst or source_id/target_id. Each nonempty src or dst
    takes precedence over its alternate key. An edge is skipped if its source
    or target has no nonempty value.

    Returns:
      - node_ids: minimal set of node ids selected
      - induced_edges: original edges among selected nodes, in input order
    """
    if weights is None:
        weights = {}
    w_distance = float(weights.get("distance", 1.0))
    w_publicness = float(weights.get("publicness", 1.0))
    w_hotspots = float(weights.get("hotspots", 1.0))

    id_to_node = {n.get("id"): n for n in nodes}
    out_adj: dict[str, set[str]] = defaultdict(set)
    in_deg: dict[str, int] = defaultdict(int)
    out_deg: dict[str, int] = defaultdict(int)

    # Build adjacency
    for e in edges:
        endpoints = _edge_endpoints(e)
        if endpoints is None:
            continue
        src, dst = endpoints
        out_adj[src].add(dst)
        out_deg[src] += 1
        in_deg[dst] += 1

    # BFS from seeds to collect candidates within radius
    dist: dict[str, int] = {s: 0 for s in seeds if s in id_to_node}
    q: deque[str] = deque(dist.keys())
    visited: set[str] = set(dist.keys())

    while q:
        cur = q.popleft()
        if dist[cur] >= radius:
            continue
        for nxt in out_adj.get(cur, ()):
            if nxt not in visited:
                visited.add(nxt)
                dist[nxt] = dist[cur] + 1
                q.append(nxt)

    # Score candidates; if hotspot unknown, fallback to out-degree
    def score(node_id: str) -> float:
        d = dist.get(node_id, 1_000_000)
        if d <= 0:
            d = 1
        node = id_to_node.get(node_id, {})
        change_freq = float(node.get("attrs", {}).get("change_freq", 0.0))
        hotspot = change_freq if change_freq > 0 else float(out_deg.get(node_id, 0))
        return (
            w_distance * (1.0 / float(d))
            + w_publicness * float(out_deg.get(node_id, 0))
            + w_hotspots * hotspot
        )

    candidates = [nid for nid in visited if nid in id_to_node]
    # Sort by score descending, breaking ties on the node id ascending.
    # ``visited`` is a set, so its iteration order is hash-randomised across
    # processes; sorting only by score leaves equal-score nodes in that
    # non-deterministic order. Using ``(-score, node_id)`` gives a stable,
    # reproducible ordering so that truncation to ``budget`` is deterministic.
    candidates.sort(key=lambda nid: (-score(nid), nid))

    selected: list[str] = []
    for nid in candidates:
        if len(selected) >= budget:
            break
        selected.append(nid)

    selected_set = set(selected)
    induced_edges = [
        e
        for e in edges
        if (endpoints := _edge_endpoints(e)) and selected_set.issuperset(endpoints)
    ]
    return selected, induced_edges
