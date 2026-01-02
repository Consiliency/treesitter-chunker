from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chunker.types import CodeChunk


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    value = max(low, min(high, value))
    return (value - low) / (high - low)


def compute_pack_hint(chunk: CodeChunk) -> float:
    """Compute a normalized [0,1] priority score for context packing.

    Inputs considered:
    - token_count (prefer smaller chunks)
    - complexity (prefer higher complexity)
    - degree (xref degree if present)
    - recent_changes (optional recency weight)

    The heuristic balances factors; callers can refine later.
    """
    md: dict[str, Any] = chunk.metadata or {}
    token_count = md.get("token_count") or 0
    complexity = (md.get("complexity") or {}).get("cyclomatic") or 0
    degree = md.get("degree") or 0
    recent_changes = md.get("recent_changes") or 0
    priority_bonus = md.get("priority") or 0

    # Smaller token count preferred → invert
    token_component = 1.0 - _normalize(float(token_count), 0.0, 2000.0)
    complexity_component = _normalize(float(complexity), 0.0, 20.0)
    degree_component = _normalize(float(degree), 0.0, 50.0)
    recency_component = _normalize(float(recent_changes), 0.0, 100.0)

    # Weighted sum
    score = (
        0.40 * token_component
        + 0.25 * complexity_component
        + 0.20 * degree_component
        + 0.10 * recency_component
        + 0.05 * _normalize(float(priority_bonus), 0.0, 1.0)
    )

    # Clamp
    return max(0.0, min(1.0, score))
