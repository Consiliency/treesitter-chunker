"""canon v1 vector-fidelity proof for the vendored serializer.

``chunker/boundary/_canon.py`` is vendored verbatim from the spec ``canon`` v1
reference impl (``canon/py/canon.py``). This module proves byte/digest fidelity
by running canon's own conformance vector suite
(``tests/fixtures/canon-vectors.json``, copied from ``canon/vectors``) through
the vendored encoder and asserting the canonical bytes and digests match the
values pinned in the vector file.

If this test fails, the vendored copy has drifted from the spec contract and the
Boundary IR can no longer be hashed soundly against other canon consumers.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from chunker.boundary import _canon

_VECTORS_PATH = Path(__file__).parent / "fixtures" / "canon-vectors.json"
_VECTORS = json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def _vector_id(vector: dict) -> str:
    return str(vector.get("name", "<unnamed>"))


@pytest.mark.parametrize("vector", _VECTORS, ids=[_vector_id(v) for v in _VECTORS])
def test_canon_vector_fidelity(vector: dict) -> None:
    """Every canon vector reproduces byte-for-byte through the vendored encoder."""
    value = _canon.decode_input(vector["input"])

    if vector.get("expect_error"):
        # Reject cases (float / NaN / Infinity / lone surrogate).
        with pytest.raises(_canon.CanonError):
            _canon.canonical_bytes(value)
        return

    expected_bytes = base64.b64decode(vector["expected_canonical_bytes_b64"])
    actual_bytes = _canon.canonical_bytes(value)
    assert actual_bytes == expected_bytes, (
        f"canon byte divergence on vector {_vector_id(vector)!r}: "
        f"vendored copy of canon/py/canon.py no longer matches the spec contract."
    )

    profile = vector["profile"]
    expected_digest = vector["expected_digest_hex"]
    actual_digest = _canon.digest(value, profile)
    assert actual_digest == expected_digest, (
        f"canon digest divergence on vector {_vector_id(vector)!r}."
    )


def test_unicode_db_is_pinned_16() -> None:
    """The vendored canon enforces the pinned Unicode 16.0 DB (fail-closed)."""
    assert _canon._ACTUAL_UNICODE == "16.0"
