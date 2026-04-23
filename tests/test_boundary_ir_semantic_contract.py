from pathlib import Path

import pytest

from chunker.boundary import (
    BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION,
    SEMANTIC_EDGE_SOURCES,
    SEMANTIC_RESOLVER_API_VERSION,
    SemanticEdge,
    SemanticResolverContext,
)
from chunker.boundary.types import DIAGNOSTIC_STAGES


def test_semantic_constants_are_frozen_and_exported():
    assert SEMANTIC_RESOLVER_API_VERSION == "1.0"
    assert BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION == "1.1"
    assert SEMANTIC_EDGE_SOURCES == ("semantic",)
    assert "semantic" in DIAGNOSTIC_STAGES


def test_semantic_context_exposes_boundary_ir_inputs():
    context = SemanticResolverContext(
        root=Path("repo"),
        language="python",
        resolution_mode="strict",
        files=({"path": "app.py"},),
        nodes=({"id": "node:a"},),
        edges=({"id": "edge:a"},),
    )

    assert context.root == Path("repo")
    assert context.language == "python"
    assert context.nodes == ({"id": "node:a"},)


def test_semantic_edge_requires_identity_and_sorts_candidates():
    edge = SemanticEdge(
        source_node_id="node:a",
        target_node_id="node:b",
        relationship_type="calls",
        resolution="resolved",
        reference="callee",
        candidates=("node:b", "node:a", "node:b"),
        confidence=1.0,
        resolver_id="test.resolver",
        resolver_version="0.1.0",
        metadata={"z": 1},
    )

    assert edge.candidates == ("node:a", "node:b")


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_semantic_confidence_accepts_inclusive_bounds(confidence: float):
    edge = SemanticEdge(
        source_node_id="node:a",
        target_node_id="node:b",
        relationship_type="calls",
        resolution="resolved",
        reference="callee",
        confidence=confidence,
        resolver_id="test.resolver",
        resolver_version="0.1.0",
    )

    assert edge.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_semantic_confidence_rejects_out_of_range_values(confidence: float):
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        SemanticEdge(
            source_node_id="node:a",
            target_node_id="node:b",
            relationship_type="calls",
            resolution="resolved",
            reference="callee",
            confidence=confidence,
            resolver_id="test.resolver",
            resolver_version="0.1.0",
        )
