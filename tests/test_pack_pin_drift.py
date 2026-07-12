"""Regression tests for the Boundary IR language-pack pin."""

from importlib import metadata

import pytest

from chunker._internal.pack_pin import resolve_pack_pin
from tests import boundary_ir_conformance


def test_resolve_pack_pin_uses_pyproject_as_the_single_source_of_truth():
    assert resolve_pack_pin() == ("0.9", "0.10")
    assert boundary_ir_conformance.PINNED_LANGUAGE_PACK == (
        ("0.9", "0.10"),
        "tree-sitter-language-pack",
    )


@pytest.mark.parametrize("drifted_version", ["0.10.0", "0.13.0"])
def test_grammar_runtime_pin_gate_rejects_pack_drift(monkeypatch, drifted_version):
    original_version = metadata.version

    def version(distribution: str) -> str:
        if distribution == "tree-sitter-language-pack":
            return drifted_version
        return original_version(distribution)

    monkeypatch.setattr(boundary_ir_conformance.metadata, "version", version)

    with pytest.raises(AssertionError, match="tree-sitter-language-pack"):
        boundary_ir_conformance.assert_grammar_runtime_pins()
