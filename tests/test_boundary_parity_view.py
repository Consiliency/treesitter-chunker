"""BUG-2: parity hash view excludes volatile fields and tolerates floats.

These tests exercise the first-class parity API
(``canonicalize_for_parity`` / ``canonicalize_for_parity_bytes`` /
``parity_digest``) that ``spec`` and other canon consumers call instead of
hand-stripping volatile fields. They are NOT covered by
``test_boundary_determinism.py`` (which hand-strips and hashes
``dumps_boundary_ir``), and crucially they exercise the FLOAT path that a default
``extract_boundary_ir`` IR never produces.
"""

from __future__ import annotations

import copy

from chunker.boundary import (
    canonicalize_for_parity,
    canonicalize_for_parity_bytes,
    parity_digest,
)


def _ir_with_float() -> dict:
    """A minimal Boundary IR carrying floats (semantic-edge confidence and
    run.options.semantic_min_confidence) -- canon rejects floats, so the parity
    view MUST pre-represent them. Mirrors the test_boundary_determinism _node_ir
    pattern but adds the float-bearing fields a real semantic IR has."""
    return {
        "schema_version": "1.0",
        "source": {"kind": "file", "path": "/abs/checkout/m.py"},
        "files": [],
        "nodes": [
            {
                "id": "n1",
                "identity": {"source": "node_id", "value": "n1"},
                "node_id": "n1",
                "definition_id": None,
                "path": "m.py",
                "span": {
                    "start_line": 1,
                    "end_line": 1,
                    "byte_start": 0,
                    "byte_end": 1,
                },
                "metadata": {},
                "relationships": [],
            }
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n1",
                "target": "n2",
                "type": "call",
                "candidates": [],
                "provenance": {"source": "semantic", "confidence": 0.9},
            }
        ],
        "diagnostics": [],
        "metrics": {"failure_buckets": {}},
        "run": {
            "tool": "treesitter-chunker",
            "tool_version": "9.9.9",
            "root": "/abs/checkout",
            "created_at": "2026-06-20T00:00:00Z",
            "canonical": True,
            "options": {"semantic_min_confidence": 0.5},
            "timings": {"total_ms": 12.345},
        },
    }


def test_parity_view_tolerates_floats():
    """canon rejects floats; the parity view must not raise on a float-bearing IR."""
    ir = _ir_with_float()
    # Must not raise -- floats are pre-represented as strings before canon.
    raw = canonicalize_for_parity_bytes(ir)
    assert isinstance(raw, bytes) and raw
    assert isinstance(parity_digest(ir), str)
    # The float survives as content (string form), not dropped.
    view = canonicalize_for_parity(ir)
    assert view["edges"][0]["provenance"]["confidence"] == repr(0.9)
    assert view["run"]["options"]["semantic_min_confidence"] == repr(0.5)


def test_parity_view_excludes_volatile_fields():
    """Mutating any of the 5 volatile fields MUST NOT change the parity bytes.

    This is the BUG-2 property; nothing else proves it. source.path,
    run.{root,created_at,tool_version,timings} are excluded from hashed content.
    """
    base = _ir_with_float()
    base_bytes = canonicalize_for_parity_bytes(base)

    mutations = [
        ("source.path", lambda ir: ir["source"].__setitem__("path", "/other/x.py")),
        ("run.root", lambda ir: ir["run"].__setitem__("root", "/totally/different")),
        ("run.created_at", lambda ir: ir["run"].__setitem__("created_at", "1999")),
        ("run.tool_version", lambda ir: ir["run"].__setitem__("tool_version", "0.0.1")),
        (
            "run.timings",
            lambda ir: ir["run"].__setitem__("timings", {"total_ms": 999.0}),
        ),
    ]
    for name, mutate in mutations:
        ir = copy.deepcopy(base)
        mutate(ir)
        assert canonicalize_for_parity_bytes(ir) == base_bytes, (
            f"parity bytes changed when only the volatile field {name!r} changed; "
            "it must be excluded from the hash view (BUG-2)."
        )


def test_parity_view_two_roots_identical():
    """The same logical IR under two absolute roots hashes identically."""
    ir_a = _ir_with_float()
    ir_a["source"]["path"] = "/checkout/alpha/m.py"
    ir_a["run"]["root"] = "/checkout/alpha"

    ir_b = _ir_with_float()
    ir_b["source"]["path"] = "/elsewhere/beta_longer/m.py"
    ir_b["run"]["root"] = "/elsewhere/beta_longer"

    assert canonicalize_for_parity_bytes(ir_a) == canonicalize_for_parity_bytes(ir_b)
    assert parity_digest(ir_a) == parity_digest(ir_b)


def test_parity_view_is_sensitive_to_content():
    """A genuine content change MUST change the parity bytes (no false parity)."""
    base = _ir_with_float()
    changed = _ir_with_float()
    changed["nodes"][0]["node_id"] = "DIFFERENT"
    changed["nodes"][0]["id"] = "DIFFERENT"
    assert canonicalize_for_parity_bytes(base) != canonicalize_for_parity_bytes(changed)
