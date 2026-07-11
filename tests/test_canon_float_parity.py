import math

import pytest

from chunker.boundary.serialization import _canon_float_str


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1e-5, "0.00001"),
        (1e-6, "0.000001"),
        (1e-7, "1e-7"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (0.1, "0.1"),
        (-0.0, "0"),
        (1.0, "1"),
        (-1.0, "-1"),
    ],
)
def test_canon_float_str_matches_js_number_to_string(value: float, expected: str):
    assert _canon_float_str(value) == expected


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canon_float_str_rejects_non_finite(value: float):
    # Non-finite floats are not valid JSON and have no canonical cross-tool
    # serialization, so the canonical IR must reject them (not emit bare
    # NaN/Infinity, which are invalid JSON).
    with pytest.raises(ValueError):
        _canon_float_str(value)


def test_semantic_edge_rejects_nan_confidence():
    """A NaN confidence must be rejected at construction, not serialized as bare NaN."""
    from chunker.boundary.semantic import SemanticEdge

    with pytest.raises(ValueError):
        SemanticEdge(
            source_node_id="a",
            relationship_type="calls",
            resolution="resolved",
            reference="b",
            resolver_id="r",
            resolver_version="1",
            confidence=math.nan,
            target_node_id="b",
        )


def test_dumps_rejects_nan_in_nested_metadata():
    """A non-finite float anywhere (e.g. nested metadata) must fail serialization,
    not emit invalid JSON `NaN`/`Infinity`."""
    from chunker.boundary.serialization import dumps_boundary_ir

    ir = {
        "schema_version": "1",
        "files": [],
        "nodes": [
            {"id": "n1", "metadata": {"score": math.nan}},
        ],
        "edges": [],
    }
    with pytest.raises(ValueError):
        dumps_boundary_ir(ir)
