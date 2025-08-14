from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any, Tuple


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

    Returns:
      - node_ids: minimal set of node ids selected
      - induced_edges: edges among selected nodes
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
        src = e.get("src") or e.get("source_id")
        dst = e.get("dst") or e.get("target_id")
        if not src or not dst:
            continue
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
    # Sort by score descending
    candidates.sort(key=score, reverse=True)

    selected: list[str] = []
    for nid in candidates:
        if len(selected) >= budget:
            break
        selected.append(nid)

    selected_set = set(selected)
    induced_edges = [
        e
        for e in edges
        if (e.get("src") in selected_set) and (e.get("dst") in selected_set)
    ]
    return selected, induced_edges
