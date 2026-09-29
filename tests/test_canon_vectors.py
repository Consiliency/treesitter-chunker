"""canon v1 vector-fidelity proof for the adapted vendored serializer.

``chunker/boundary/_canon.py`` adapts only Unicode backend loading from the spec
``canon`` v1 reference impl (``canon/py/canon.py``). This proves byte/digest fidelity
by running canon's own conformance vector suite
(``tests/fixtures/canon-vectors.json``, copied from ``canon/vectors``) through
the vendored encoder and asserting the canonical bytes and digests match the
values pinned in the vector file.

If this test fails, the vendored copy has drifted from the spec contract and the
Boundary IR can no longer be hashed soundly against other canon consumers.
"""

from __future__ import annotations

import base64
import builtins
import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from packaging.requirements import Requirement

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
    assert (
        actual_digest == expected_digest
    ), f"canon digest divergence on vector {_vector_id(vector)!r}."


def test_unicode_db_is_pinned_16() -> None:
    """The vendored canon enforces the pinned Unicode 16.0 DB (fail-closed)."""
    assert _canon._ACTUAL_UNICODE == "16.0"
    assert _canon.unicodedata.unidata_version == "16.0.0"


def _load_canon_with_tables(
    stdlib_version: str, backport_version: str | None
) -> tuple[dict, list[str]]:
    source = Path(_canon.__file__).read_text(encoding="utf-8")
    imported: list[str] = []

    def controlled_import(name: str, *args: object, **kwargs: object) -> ModuleType:
        if name == "unicodedata":
            return stdlib
        if name == "unicodedata2":
            imported.append(name)
            if backport_version is None:
                raise ImportError("unicodedata2 unavailable")
            return backport
        return builtins.__import__(name, *args, **kwargs)

    stdlib = ModuleType("unicodedata")
    stdlib.unidata_version = stdlib_version
    backport = ModuleType("unicodedata2")
    backport.unidata_version = backport_version
    namespace = {"__builtins__": {**vars(builtins), "__import__": controlled_import}}
    exec(compile(source, str(_canon.__file__), "exec"), namespace)  # noqa: S102
    return namespace, imported


def test_exact_stdlib_tables_skip_backport() -> None:
    namespace, imported = _load_canon_with_tables("16.0.0", None)
    assert namespace["unicodedata"].__name__ == "unicodedata"
    assert imported == []


@pytest.mark.parametrize("stdlib_version", ["15.0.0", "16.0.1", "17.0.0"])
def test_other_stdlib_tables_use_exact_backport(stdlib_version: str) -> None:
    namespace, imported = _load_canon_with_tables(stdlib_version, "16.0.0")
    assert namespace["unicodedata"].__name__ == "unicodedata2"
    assert imported == ["unicodedata2"]


def test_missing_backport_fails_closed() -> None:
    with pytest.raises(ImportError, match="unicodedata2==16.0.0"):
        _load_canon_with_tables("17.0.0", None)


@pytest.mark.parametrize("backport_version", ["15.0.0", "16.0.1", "17.0.0"])
def test_mismatched_backport_fails_closed(backport_version: str) -> None:
    with pytest.raises(RuntimeError, match=f"got {backport_version}"):
        _load_canon_with_tables("15.0.0", backport_version)


@pytest.mark.parametrize(
    ("python_version", "implementation", "requires_backport"),
    [
        ("3.11", "CPython", True),
        ("3.12", "CPython", True),
        ("3.13", "CPython", True),
        ("3.14", "CPython", False),
        ("3.15", "CPython", True),
        ("3.14", "PyPy", True),
    ],
)
def test_backport_requirement_marker(
    python_version: str, implementation: str, requires_backport: bool
) -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    requirement = next(
        Requirement(item)
        for item in metadata["project"]["dependencies"]
        if Requirement(item).name == "unicodedata2"
    )
    assert str(requirement.specifier) == "==16.0.0"
    marker = requirement.marker
    assert marker is not None
    assert (
        marker.evaluate(
            {
                "python_version": python_version,
                "platform_python_implementation": implementation,
            }
        )
        is requires_backport
    )
