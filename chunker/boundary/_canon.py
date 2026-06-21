"""Vendored copy of canon v1 — the spec canonical serialization contract (S1).

VENDORED, DO NOT EDIT BY HAND. Source of truth:
    spec repo: canon/py/canon.py  (contract: canon/SPEC.md)
    source sha256: 53b9447a7f21dc05fabb3fb2505aadad2d494fc79f2ae60970ecfc8c6852bce0

canon is not yet pip-installable, so it is vendored here verbatim to guarantee
byte-for-byte fidelity with the spec reference impl. Fidelity is proven against
the canon conformance vectors in tests/test_canon_vectors.py. To update, re-copy
canon/py/canon.py from spec, refresh the sha256 above, and re-run that test.

Requires: unicodedata2==16.0.0 (pinned Unicode 16.0 DB; see canon/SPEC.md S5).
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Tuple

# --------------------------------------------------------------------------- #
# Unicode database pin (SPEC.md section 5) — load-bearing for cross-language byte-identity.
#
# NFC is defined against a Unicode version. Stdlib ``unicodedata`` is bound to whatever Unicode DB
# the host CPython was built with (3.10 ships 13.0.0; newer builds differ), so it cannot guarantee
# the SAME NFC as the TS port (Node ICU). We pin a maintained PyPI backport, ``unicodedata2``,
# exactly to Node's Unicode version (16.0) and use it for ALL NFC. See canon/py/requirements.txt
# for the exact pin; the assertion below is fail-closed so a wrong build can NEVER silently diverge.
# --------------------------------------------------------------------------- #
EXPECTED_UNICODE = "16.0"  # major.minor; matches Node's process.versions.unicode

try:
    import unicodedata2 as unicodedata  # pinned Unicode 16.0 DB (see requirements.txt)
except ImportError as exc:  # pragma: no cover - environment misconfiguration
    raise ImportError(
        "canon requires the pinned 'unicodedata2' backport for a deterministic Unicode DB "
        "(install canon/py/requirements.txt: unicodedata2==16.0.0). Stdlib 'unicodedata' is bound "
        "to the host CPython build and would NOT match the TypeScript port byte-for-byte."
    ) from exc


def _unicode_major_minor(version: str) -> str:
    """Reduce a Unicode version string (e.g. '16.0.0') to 'major.minor' (e.g. '16.0')."""
    return ".".join(version.split(".")[:2])


# Fail-closed version assertion (SPEC.md section 5). A mismatch here means the NFC DB in use is NOT
# the pinned one, which is a determinism hole for a parity engine — so we refuse to load rather than
# emit silently-divergent bytes. unicodedata2 reports e.g. '16.0.0'; Node reports '16.0'.
_ACTUAL_UNICODE = _unicode_major_minor(unicodedata.unidata_version)
if _ACTUAL_UNICODE != EXPECTED_UNICODE:
    raise RuntimeError(
        "canon Unicode DB mismatch: expected %s, got %s (from unicodedata2 %s). NFC determinism "
        "across the Python and TypeScript ports is not guaranteed; refusing to load."
        % (EXPECTED_UNICODE, _ACTUAL_UNICODE, unicodedata.unidata_version)
    )

# SPEC.md section 8 — the four digest profiles. ``locator`` is intentionally NOT a profile.
PROFILES = ("semantic-content", "run", "artifact-byte", "certificate")
_DOMAIN_PREFIX = "spec-canon:v1:"


class CanonError(ValueError):
    """Raised for any value outside the supported canonical domain (SPEC.md section 1/6)."""


# --------------------------------------------------------------------------- #
# String encoding (SPEC.md section 5)
# --------------------------------------------------------------------------- #

def _encode_string(s: str) -> str:
    # NFC normalize first (also applied to keys before sorting, see _encode_object).
    s = unicodedata.normalize("NFC", s)
    out = ['"']
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            # Unpaired surrogate: not valid scalar text. Python would raise on UTF-8 encode while
            # JS emits U+FFFD -> silent byte-divergence. Reject in BOTH (SPEC.md section 5).
            raise CanonError("unpaired surrogate U+%04X is not allowed in canonical content" % cp)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif cp <= 0x1F:
            # Control chars: \uXXXX lowercase hex. No short escapes (no \n, \t, ...).
            out.append("\\u%04x" % cp)
        else:
            # Everything else, incl. all non-ASCII and U+007F, is raw (ensure_ascii=False).
            out.append(ch)
    out.append('"')
    return "".join(out)


# --------------------------------------------------------------------------- #
# Number encoding (SPEC.md section 6) — integers only.
# --------------------------------------------------------------------------- #

def _encode_int(value: int) -> str:
    # bool is handled earlier; here value is a genuine int. str(int) is exactly the canonical
    # shortest decimal form: optional '-', no leading zeros (except '0'), no '+', no exponent.
    return str(value)


# --------------------------------------------------------------------------- #
# Object encoding (SPEC.md sections 3, 7) — keys NFC'd then sorted by code point.
# --------------------------------------------------------------------------- #

def _encode_object(obj: dict) -> str:
    # Normalize keys to NFC before sorting; detect collisions.
    normalized: dict[str, Any] = {}
    for k, v in obj.items():
        if not isinstance(k, str):
            raise CanonError("object keys must be strings, got %r" % type(k).__name__)
        nk = unicodedata.normalize("NFC", k)
        if nk in normalized:
            raise CanonError("key collision after NFC normalization: %r" % nk)
        normalized[nk] = v
    # Python str comparison is already by Unicode code point — correct for astral chars.
    keys = sorted(normalized.keys())
    parts = []
    for k in keys:
        parts.append(_encode_string(k) + ":" + _encode_value(normalized[k]))
    return "{" + ",".join(parts) + "}"


def _encode_array(arr: Iterable) -> str:
    # Insertion order preserved ALWAYS (SPEC.md section 4). Never sort.
    return "[" + ",".join(_encode_value(v) for v in arr) + "]"


# --------------------------------------------------------------------------- #
# Value dispatch — bool BEFORE int (SPEC.md section 6 boolean trap).
# --------------------------------------------------------------------------- #

def _encode_value(value: Any) -> str:
    # Reject markers from the type-tagged decoder (SPEC.md section 2/6).
    if isinstance(value, FloatMarker):
        raise CanonError("floats are forbidden in canonical content; pre-represent as int or string")
    if isinstance(value, NanMarker):
        raise CanonError("NaN is forbidden in canonical content")
    if isinstance(value, InfMarker):
        raise CanonError("Infinity is forbidden in canonical content")
    if value is None:
        return "null"
    if isinstance(value, bool):  # MUST precede int: isinstance(True, int) is True.
        return "true" if value else "false"
    if isinstance(value, int):
        return _encode_int(value)
    if isinstance(value, float):
        raise CanonError("floats are forbidden in canonical content; pre-represent as int or string")
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, dict):
        return _encode_object(value)
    if isinstance(value, (list, tuple)):
        return _encode_array(value)
    raise CanonError("unsupported type for canonical content: %s" % type(value).__name__)


# --------------------------------------------------------------------------- #
# Public API (SPEC.md sections 8, 9)
# --------------------------------------------------------------------------- #

def canonical_bytes(value: Any) -> bytes:
    """Deterministic canonical UTF-8 bytes for a value in the supported domain."""
    return _encode_value(value).encode("utf-8")


def _strip_top_level_digest(value: Any) -> Any:
    # SPEC.md section 8: exclude a top-level ``digest`` key only (nested is ordinary content).
    if isinstance(value, dict) and "digest" in value:
        return {k: v for k, v in value.items() if k != "digest"}
    return value


def digest(value: Any, profile: str) -> str:
    """Lowercase-hex SHA-256 over domain_prefix(profile) || canonical_bytes(value)."""
    if profile not in PROFILES:
        raise CanonError("unknown digest profile: %r (allowed: %s)" % (profile, ", ".join(PROFILES)))
    prefix = (_DOMAIN_PREFIX + profile + "\n").encode("ascii")
    body = canonical_bytes(_strip_top_level_digest(value))
    return hashlib.sha256(prefix + body).hexdigest()


# --------------------------------------------------------------------------- #
# Content/envelope split (SPEC.md section 10)
# --------------------------------------------------------------------------- #

def split_record(record: dict, content_keys: Iterable[str]) -> Tuple[dict, dict]:
    """Split a record into (content, envelope). Only ``content`` is ever hashed."""
    keyset = set(content_keys)
    content = {k: v for k, v in record.items() if k in keyset}
    envelope = {k: v for k, v in record.items() if k not in keyset}
    return content, envelope


# --------------------------------------------------------------------------- #
# Type-tagged input decoder (SPEC.md section 2) — test harness, identical across languages.
# --------------------------------------------------------------------------- #

class FloatMarker:
    """A value the encoder must reject (stands in for a float literal)."""


class NanMarker:
    pass


class InfMarker:
    def __init__(self, sign: int):
        self.sign = sign


def decode_input(node: Any) -> Any:
    """Decode a type-tagged vector input tree into native values (or reject markers)."""
    if isinstance(node, dict) and len(node) == 1:
        (tag, payload), = node.items()
        if tag == "$int":
            return int(payload)  # decimal string -> arbitrary-precision int
        if tag == "$float":
            return FloatMarker()
        if tag == "$nan":
            return NanMarker()
        if tag == "$inf":
            return InfMarker(1 if payload >= 0 else -1)
        if tag == "$str":
            return payload
        if tag == "$bool":
            return bool(payload)
        if tag == "$null":
            return None
        if tag == "$obj":
            return {k: decode_input(v) for k, v in payload.items()}
        if tag == "$arr":
            return [decode_input(v) for v in payload]
        # one-key dict that is not a tag: fall through to plain-dict handling
    if isinstance(node, dict):
        return {k: decode_input(v) for k, v in node.items()}
    if isinstance(node, list):
        return [decode_input(v) for v in node]
    # bare scalars: str/bool/None pass through; a bare JSON number is treated as int if integral.
    if isinstance(node, bool):
        return node
    if isinstance(node, int):
        return node
    if isinstance(node, float):
        # Bare JSON float in a vector input -> a float marker (encoder rejects).
        return FloatMarker()
    return node
