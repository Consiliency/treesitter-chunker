"""Optional semantic Boundary IR enrichment contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .types import ResolutionMode, ResolutionStatus


@dataclass(frozen=True)
class SemanticResolverContext:
    """Read-only inputs passed to optional semantic resolvers."""

    root: Path
    language: str | None
    resolution_mode: ResolutionMode
    files: tuple[dict[str, Any], ...]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SemanticEdge:
    """Supplemental semantic edge emitted by an opt-in resolver."""

    source_node_id: str
    relationship_type: str
    resolution: ResolutionStatus
    reference: str
    resolver_id: str
    resolver_version: str
    confidence: float
    target_node_id: str | None = None
    candidates: tuple[str, ...] = ()
    location: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_node_id:
            raise ValueError("SemanticEdge.source_node_id is required")
        if not self.relationship_type:
            raise ValueError("SemanticEdge.relationship_type is required")
        if not self.reference:
            raise ValueError("SemanticEdge.reference is required")
        if not self.resolver_id:
            raise ValueError("SemanticEdge.resolver_id is required")
        if not self.resolver_version:
            raise ValueError("SemanticEdge.resolver_version is required")
        if self.resolution not in {"resolved", "ambiguous", "unresolved"}:
            raise ValueError(f"Unsupported semantic resolution: {self.resolution}")
        if self.target_node_id is None and not self.reference:
            raise ValueError("SemanticEdge requires target_node_id or reference")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("SemanticEdge.confidence must be in [0.0, 1.0]")
        object.__setattr__(
            self,
            "candidates",
            tuple(
                sorted(dict.fromkeys(str(candidate) for candidate in self.candidates))
            ),
        )


@runtime_checkable
class SemanticResolver(Protocol):
    """Protocol implemented by optional semantic enrichment providers."""

    resolver_id: str
    resolver_version: str
    supported_languages: tuple[str, ...]

    def enrich(self, context: SemanticResolverContext) -> Iterable[SemanticEdge]:
        """Yield semantic edges for the supplied Boundary IR context."""
