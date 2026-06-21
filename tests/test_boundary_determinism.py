"""P0 bug-lock: bidirectional determinism regression suite for the Boundary IR.

This module is the red->green traceability spine for the ``treesitter-chunker``
P0/P1 roadmap (``private-repo-audit/roadmaps/treesitter-chunker.md``). It LOCKS
the demonstrated determinism bugs before they are fixed.

Status of each test in THIS commit (no production code is changed in P0):

* Five tests are **RED** -- they assert the *correct* (post-fix) behavior and
  therefore FAIL against the current serializer/adapter. Each failure is the
  documented bug; the divergent/equal bytes are captured inline as evidence.
  These five turn GREEN in P1 once ``canon`` v1 is adopted.
* One test is **GREEN** -- ``test_reordered_candidates_same_hash`` guards a
  genuine set-semantic field so P1 does not over-correct and start treating
  order-insensitive id lists as order-significant.

Frozen test IDs (referenced verbatim by the P1/P2 exit gates):

* ``test_reordered_params_change_hash``      (RED -- false parity, serialization.py:33-34)
* ``test_reordered_imports_change_hash``     (RED -- false parity + de-dup, adapter.py:95-96)
* ``test_reordered_candidates_same_hash``    (GREEN -- set-semantic guard)
* ``test_two_roots_same_parity_hash``        (RED -- absolute path leak)
* ``test_cold_vs_incremental_same_bytes``    (RED -- cold/incremental path divergence + BUG-4)
* ``test_node_id_uses_relative_path``        (RED -- node_id bakes the absolute path)

--------------------------------------------------------------------------------
BUG-1b INVESTIGATION (blocking P1 sort-decision input) -- ANSWERED
--------------------------------------------------------------------------------

Question (remediation BUG-1b): are ``metadata.{dependencies,exports,imports}``
(adapter.py:160-168) and semantic ``candidates`` emitted in *deterministic
source order*, or is their order nondeterministic?

Finding (traced through ``chunker/core.py`` + ``chunker/metadata/languages/*``):

* ``metadata.dependencies`` -- extracted as a ``set`` (e.g. go.py:131,
  rust.py:181 ``extract_dependencies -> set[str]``) and explicitly
  ``sorted(...)`` at ``core.py:596``. A set has no source order, so sorting is
  the only way to make it deterministic. **Set-semantic; NOT order-significant.**
* ``metadata.exports`` -- explicitly ``sorted(...)`` at ``core.py:609``.
  Per-language extractors collect exported names; the public-symbol *set* of a
  unit carries no meaningful order. **Set-semantic; NOT order-significant.**
* ``metadata.imports`` -- stored in extractor source order at ``core.py:604``
  (``metadata["imports"] = imports``, no sort), so at the raw chunk layer it
  IS order-significant (import order can matter, e.g. side-effecting imports).
  HOWEVER it is then re-sorted twice before emission: once by
  ``_normalize_text_list`` -> ``sorted(dict.fromkeys(...))`` (core.py:143-156,
  called at core.py:238) when building retrieval metadata, and again by the
  Boundary adapter's ``_stable_value`` (adapter.py:90-100). So the *emitted*
  ``metadata.imports`` is lexicographically sorted and de-duplicated -- its
  real source order is destroyed.
* semantic ``candidates`` -- ``list(edge.candidates)`` (adapter.py); candidates
  is the *set* of resolution targets for an ambiguous edge -> genuinely
  order-insensitive. **Set-semantic.**

P1 DECISION (recorded as a P1 input):

* ``dependencies``, ``exports``, ``candidates`` are set-semantic -> sort them
  deterministically AT CONSTRUCTION (not via the content-sniff serializer
  branch that P1 deletes).
* ``imports`` is order-significant at the source but is currently sorted to
  mask nondeterminism. Per canon rule "never sort to mask": P1 must PRESERVE
  the extractor's source order for ``imports`` end to end (drop the
  ``_normalize_text_list`` sort and the ``_stable_value`` sort on this field),
  OR, if the import extraction order is itself proven nondeterministic, fix it
  AT THE SOURCE (order by source byte position) -- never sort to hide it.
  ``test_reordered_imports_change_hash`` locks this: after P1 a reordered
  import list MUST change the canonical bytes.
"""

from __future__ import annotations

import copy
import hashlib
import os

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.adapter import _stable_value
from chunker.boundary.impact import normalize_boundary_path
from chunker.boundary.serialization import _canonicalize_value

# A function with two order-significant parameters. ``a`` then ``b`` is a
# different program contract than ``b`` then ``a`` (call sites bind positionally).
_SRC_AB = "def f(a, b):\n    return a + b\n"


def _hash(ir: dict) -> str:
    """Parity hash = sha256 over the canonical Boundary IR bytes.

    This mirrors exactly what a downstream consumer (``spec``) does: serialize
    via the public canonical serializer and hash the resulting bytes.
    """
    return hashlib.sha256(dumps_boundary_ir(ir).encode("utf-8")).hexdigest()


def _strip_volatile(ir: dict) -> dict:
    """Drop the known-volatile run/source fields so a test can isolate a *different*
    leak (e.g. an absolute path baked into ``node_id``) from the already-known
    ``run.root``/``source.path`` leak.

    NOTE: this hand-stripping is a TEST crutch. P1 must provide a first-class
    ``canonicalize_for_parity()`` / ``hash_view=True`` API (BUG-2) so consumers
    never hand-strip. Until then, stripping here lets the RED tests pinpoint the
    *second* leak rather than tripping only on ``run.root``.
    """
    ir = copy.deepcopy(ir)
    run = ir.get("run")
    if isinstance(run, dict):
        run["root"] = "<ROOT>"
        run["created_at"] = None
        run["tool_version"] = None
        run.pop("timings", None)
    source = ir.get("source")
    if isinstance(source, dict):
        source["path"] = "<ROOT>"
    return ir


def _node_ir(metadata_list_field: str, items: list[str]) -> dict:
    """Build a minimal, valid Boundary IR with a single node carrying one
    order-significant string list in ``metadata`` -- isolates the serializer's
    list handling from the extractor."""
    return {
        "schema_version": "1.0",
        "source": {"kind": "file", "path": "m.py"},
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
                "metadata": {metadata_list_field: list(items)},
            }
        ],
        "edges": [],
        "diagnostics": [],
        "run": {"root": ".", "created_at": None, "tool_version": None},
    }


# ---------------------------------------------------------------------------
# (1) RED -- false parity on order-significant string lists (BUG-1).
#     Site: chunker/boundary/serialization.py:33-34 (_canonicalize_value).
# ---------------------------------------------------------------------------
def test_reordered_params_change_hash():
    """``params=["b","a"]`` and ``params=["a","b"]`` are DIFFERENT logical inputs
    and MUST produce different canonical bytes.

    GREEN after P1. ``_canonicalize_value`` no longer content-sniff-sorts
    all-string lists (canon S4: array order is preserved ALWAYS), so a real
    parameter reorder is now visible to a hash check (no false parity).
    """
    # The content-sniff branch is gone: order is preserved verbatim.
    assert _canonicalize_value(["b", "a"]) == ["b", "a"]

    forward = _node_ir("params", ["a", "b"])
    reordered = _node_ir("params", ["b", "a"])

    # Sensitivity property: different order -> different bytes.
    assert _hash(forward) != _hash(reordered), (
        "reordered params must hash differently -- the serializer must preserve "
        "list insertion order (canon S4)."
    )


# ---------------------------------------------------------------------------
# (2) RED -- false parity + silent de-dup on imports (BUG-1 via _stable_value).
#     Site: chunker/boundary/adapter.py:95-96 (_stable_value).
# ---------------------------------------------------------------------------
def test_reordered_imports_change_hash():
    """A reordered ``metadata.imports`` list MUST change the canonical bytes.

    GREEN after P1. ``_stable_value`` no longer runs ``sorted(dict.fromkeys(...))``
    on all-string lists -- it preserves list/tuple order verbatim (canon S4) and
    no longer silently de-duplicates. ``imports`` is order-significant (BUG-1b):
    a reorder is a different logical value and now hashes differently.
    """
    # The all-strings sort+dedup branch is gone: order AND duplicates preserved.
    assert _stable_value({"imports": ["b", "a", "b"]}) == {"imports": ["b", "a", "b"]}
    assert _stable_value({"imports": ["a", "b"]}) == {"imports": ["a", "b"]}

    forward = _node_ir("imports", ["alpha", "beta"])
    reordered = _node_ir("imports", ["beta", "alpha"])

    assert _hash(forward) != _hash(reordered), (
        "reordered imports must hash differently -- _stable_value and the "
        "serializer must preserve list order (canon S4; imports order-significant)."
    )


# ---------------------------------------------------------------------------
# (3) GREEN -- set-semantic field guard (anti-over-correction for P1).
# ---------------------------------------------------------------------------
def test_reordered_candidates_same_hash():
    """A reordered *set-semantic* field (``edge.candidates``) MUST hash the same.

    CURRENTLY GREEN and MUST STAY GREEN. ``candidates`` is the set of resolution
    targets for an ambiguous edge -- order carries no meaning. Today the
    content-sniff sort makes this pass; in P1, after that sort is deleted, the
    same guarantee must come from sorting ``candidates`` AT CONSTRUCTION. This
    test ensures P1 does not swing too far and make genuine set fields
    order-significant.
    """

    def edge_ir(candidates: list[str]) -> dict:
        return {
            "schema_version": "1.0",
            "source": {"kind": "file", "path": "m.py"},
            "files": [],
            "nodes": [],
            "edges": [
                {
                    "id": "e1",
                    "source": "a",
                    "target": "b",
                    "type": "call",
                    "candidates": list(candidates),
                }
            ],
            "diagnostics": [],
            "run": {"root": ".", "created_at": None, "tool_version": None},
        }

    assert _hash(edge_ir(["x", "y", "z"])) == _hash(
        edge_ir(["z", "y", "x"])
    ), "candidates is set-semantic: reordering it MUST NOT change the hash."


# ---------------------------------------------------------------------------
# (4) RED -- absolute-path leak breaks cross-machine stability (BUG-2/BUG-3).
#     Sites: node_id from raw caller path (core.py chunk_file -> chunk_text);
#     run.root/source.path stored as str(root) (adapter.py:866,899,1151,1184);
#     all survive canonicalization (serialization.py:79-84).
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="P0 bug-lock: node_id + semantic_text bake the absolute root path; turns green in P1",
)
def test_two_roots_same_parity_hash(tmp_path):
    """The SAME snapshot extracted under two DIFFERENT absolute checkout roots
    MUST produce identical PARITY bytes (stability / no false negatives).

    CURRENTLY RED. Even after hand-stripping the known-volatile ``run.root`` /
    ``source.path`` (see ``_strip_volatile``), the bytes still differ because
    ``node_id`` is computed from the raw absolute caller path
    (``compute_node_id(file_path=str(path), ...)`` via ``chunk_file``), and the
    absolute path also leaks into ``metadata.semantic_text``. Two machines with
    different checkout locations therefore hash the same code differently ->
    false negative on a parity check.

    Captured evidence (this tree): with roots ``/tmp/alpha_*`` vs
    ``/tmp/beta_longer_*`` and identical ``m.py``:
        node_id(rootA) != node_id(rootB)            # path baked into the hash
        semantic_text contains the absolute "/tmp/alpha_.../m.py"
        _hash(strip(irA)) != _hash(strip(irB))      # leak survives stripping
    """
    root_a = tmp_path / "alpha"
    root_b = tmp_path / "beta_longer_name"
    for root in (root_a, root_b):
        root.mkdir()
        (root / "m.py").write_text(_SRC_AB, encoding="utf-8")

    ir_a = extract_boundary_ir(str(root_a), "python")
    ir_b = extract_boundary_ir(str(root_b), "python")

    assert _hash(_strip_volatile(ir_a)) == _hash(_strip_volatile(ir_b)), (
        "ABS-PATH LEAK: same snapshot under two roots hashed differently even "
        "after stripping run.root/source.path -- node_id (and semantic_text) "
        "bake the absolute path; they must key on the repo-relative path."
    )


# ---------------------------------------------------------------------------
# (5) RED -- cold vs incremental path normalization diverges (BUG-4).
#     Cold uses _display_path (no normalize, adapter.py:1007); incremental uses
#     normalize_boundary_path(_display_path(...)) (adapter.py:632); and
#     normalize_boundary_path (impact.py:11-12) only swaps backslashes -- it does
#     NOT collapse ./, .., or redundant separators.
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="P0 bug-lock: normalize_boundary_path incomplete (BUG-4), cold vs incremental diverge; turns green in P1",
)
def test_cold_vs_incremental_same_bytes(tmp_path, monkeypatch):
    """``incremental=False`` and ``incremental=True`` on identical input MUST
    produce identical canonical bytes.

    CURRENTLY RED (platform-latent; surfaced deterministically here). On POSIX
    the two paths happen to coincide, so to expose the documented divergence on
    any platform we monkeypatch ``_display_path`` to emit a Windows-style
    backslash separator (what a real Windows checkout produces). Then:

      * cold keeps the backslash display path verbatim     -> file/path "pkg\\m.py"
      * incremental runs it through ``normalize_boundary_path`` -> "pkg/m.py"

    and ``file_id``/``node_id`` (keyed on the display path) diverge with it.

    Captured evidence (this tree, with the monkeypatch):
        cold file path: "pkg\\m.py"
        incr file path: "pkg/m.py"
        _hash(strip(cold)) != _hash(strip(incr))

    Underlying BUG-4 (also asserted directly): ``normalize_boundary_path`` is
    incomplete -- it only swaps backslashes:
        normalize_boundary_path("./a/b.py") == "./a/b.py"   # './' NOT collapsed
        normalize_boundary_path("a/../b.py") == "a/../b.py"  # '..' NOT collapsed
        normalize_boundary_path("a//b.py")  == "a//b.py"     # '//' NOT collapsed
    """
    # BUG-4: normalize_boundary_path is not total (drives the divergence below).
    assert normalize_boundary_path("./a/b.py") == "./a/b.py"
    assert normalize_boundary_path("a/../b.py") == "a/../b.py"
    assert normalize_boundary_path("a//b.py") == "a//b.py"

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text(_SRC_AB, encoding="utf-8")
    cache_dir = tmp_path / "cache"

    from chunker.boundary import adapter

    real_display_path = adapter._display_path

    def windows_display_path(file_path, root):
        # Simulate a Windows checkout: the relative display path uses backslashes.
        return real_display_path(file_path, root).replace("/", "\\")

    monkeypatch.setattr(adapter, "_display_path", windows_display_path)

    cold = extract_boundary_ir(str(tmp_path), "python", incremental=False)
    incremental = extract_boundary_ir(
        str(tmp_path),
        "python",
        incremental=True,
        cache_dir=str(cache_dir),
        force_rebuild=True,
    )

    assert _hash(_strip_volatile(cold)) == _hash(_strip_volatile(incremental)), (
        "COLD/INCREMENTAL DIVERGENCE: cold leaves the display path un-normalized "
        "while incremental normalizes it -- and normalize_boundary_path is "
        "incomplete (BUG-4). Path normalization must be unified and total, "
        "applied once before every ID and serialized path."
    )


# ---------------------------------------------------------------------------
# (6) RED -- node_id must key on a repo-relative path, not an absolute one.
#     Site: node_id from raw caller path (core.py:983 compute_node_id with
#     file_path=str(path)); file_id/definition_id key on the relative display
#     path -> within one IR the IDs are mutually inconsistent + non-portable.
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True, reason="P0 bug-lock: node_id uses absolute path; turns green in P1"
)
def test_node_id_uses_relative_path(tmp_path):
    """A node's ``node_id`` MUST key on the repo-relative path (the same form as
    ``file_id``/``definition_id``), NOT on the absolute caller path.

    CURRENTLY RED. ``chunk_file`` -> ``chunk_text`` computes ``node_id`` with
    ``file_path=str(path)`` (an absolute path; core.py:983), while the Boundary
    layer recomputes ``file_id``/``definition_id`` from the relative display
    path. So ``node_id`` keys on the absolute checkout root: it differs across
    machines and is mutually inconsistent with the other IDs in the same IR.

    Proven exactly: the emitted ``node_id`` equals
    ``compute_node_id(<ABS path>, ...)`` and does NOT equal
    ``compute_node_id(<relative path>, ...)``.

    Captured evidence (this tree): the absolute root also leaks verbatim into
    the serialized node via ``metadata.semantic_text``.
    """
    from chunker.core import chunk_file
    from chunker.types import compute_node_id

    root = tmp_path / "myrepo"
    root.mkdir()
    src_file = root / "m.py"
    src_file.write_text(_SRC_AB, encoding="utf-8")

    ir = extract_boundary_ir(str(root), "python")
    assert ir["nodes"], "expected at least one node"
    node = ir["nodes"][0]

    # Recompute node_id from the relative display path. This is what node_id
    # SHOULD equal once IDs key on the repo-relative POSIX path.
    chunk = chunk_file(str(src_file), "python")[0]
    node_id_from_relative = compute_node_id(
        "m.py", chunk.language, chunk.parent_route, chunk.content
    )

    assert node["node_id"] == node_id_from_relative, (
        "node_id IS NOT RELATIVE: emitted node_id keys on the absolute caller "
        "path (core.py:983 compute_node_id with file_path=str(path)) instead of "
        "the repo-relative path used by file_id/definition_id."
    )

    # Portability corollary: the absolute checkout root must not leak verbatim
    # into the serialized node payload (this catches the semantic_text leak).
    abs_sep = str(root) + os.sep
    assert abs_sep not in dumps_boundary_ir({**ir, "run": {}, "source": {}}), (
        "ABS-PATH LEAK: the absolute checkout root appears in the serialized "
        "node payload (metadata.semantic_text)."
    )
