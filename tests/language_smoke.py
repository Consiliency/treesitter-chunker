"""Shared language-coverage smoke harness (the honest per-language audit).

This is the single source of truth for the language-coverage smoke sweep across
the *entire* tree-sitter-language-pack. It is consumed by:

  * ``scripts/regenerate_language_coverage.py`` -- produces the committed
    ``docs/language-coverage.json`` + ``docs/language-coverage.md`` report.
  * ``tests/test_language_smoke.py`` -- the continuous smoke-tier CI gate that
    recomputes the sweep live and diffs it against the committed JSON oracle.

Two tiers, deliberately honest about what each proves:

LOAD tier (comprehensive, cheap)
    Every language enumerated by the pinned pack is loaded and made to parse a
    trivial input. ``LOADS`` vs ``FAILS_TO_LOAD`` (the C#/ABI-15 class). Under
    the verified-byte-stable pin (tree_sitter 0.25 + pack 0.9.0) every pack
    grammar is expected to load; the gate's value is forward drift detection --
    a future ABI break that silently breaks a language turns this RED.

EXTRACTION tier (best-effort, for the languages we can author a valid sample for)
    The 12 golden languages route through their authoritative golden fixture
    repos (``tests/fixtures/boundary_ir/repos``); the remaining
    extension-mapped languages route through tiny curated samples under
    ``tests/fixtures/language_smoke/samples``. Each is classified by the number
    of *distinct boundary kinds* it emits (NOT node count, which is sample-
    fragile):

      RICH          >= 2 distinct kinds
      SPARSE        == 1 distinct kind (the pre-fix C++ class -- a thin surface)
      EMPTY         parsed cleanly but emitted 0 boundaries
      EXTRACTION_GAP chunker advertises the extension but no parser resolves
                     (status=error: the IR records "Language 'X' not found").
                     A real fixable coverage bug, surfaced not patched.

    Languages with no curated sample (the long tail) are ``LOAD_ONLY`` --
    honestly *not* extraction-tested rather than guessed EMPTY.

The pack is held at 0.9.0 on purpose: that is the byte-stable pairing with
tree_sitter 0.25. ``assert_grammar_runtime_pins`` (imported from the boundary
conformance harness) fails closed if either drifts off-pin.
"""

from __future__ import annotations

import typing
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_ROOT = Path("tests/fixtures/language_smoke/samples")
GOLDEN_REPOS_ROOT = Path("tests/fixtures/boundary_ir/repos")

# Load classifications.
LOADS = "loads"
FAILS_TO_LOAD = "fails_to_load"

# Extraction classifications.
RICH = "rich"
SPARSE = "sparse"
EMPTY = "empty"
EXTRACTION_GAP = "extraction_gap"
LOAD_ONLY = "load_only"

# The 12 languages held to a committed golden + non-empty guarantee by the deep
# determinism gate. The smoke sweep routes these through their authoritative
# golden fixture repos so their extraction surface reflects a real codebase, not
# a thin hand-authored snippet (a thin sample mislabels e.g. C as SPARSE).
GOLDEN_LANGUAGES = (
    "c",
    "cpp",
    "csharp",
    "go",
    "java",
    "javascript",
    "kotlin",
    "php",
    "python",
    "ruby",
    "swift",
    "typescript",
)

# Non-golden, extension-mapped languages -> curated sample filename. These are
# the languages chunker can route a file to via its EXTENSION_MAP, for which we
# author a tiny *valid* sample so the extraction tier feeds parsers real (not
# garbage) input. The long tail of pack languages with no entry here is reported
# LOAD_ONLY -- honestly not extraction-tested.
SAMPLE_LANGUAGES: dict[str, str] = {
    "rust": "sample.rs",
    "scala": "sample.scala",
    "dart": "sample.dart",
    "lua": "sample.lua",
    "r": "sample.r",
    "julia": "sample.jl",
    "elixir": "sample.ex",
    "clojure": "sample.clj",
    "ocaml": "sample.ml",
    "elisp": "sample.el",
    "erlang": "sample.erl",
    "fsharp": "sample.fs",
    "nim": "sample.nim",
    "perl": "sample.pl",
    "powershell": "sample.ps1",
    "bash": "sample.sh",
    "vim": "sample.vim",
    "zig": "sample.zig",
    "sql": "sample.sql",
    "matlab": "sample.m",
    "cobol": "sample.cob",
    "fortran": "sample.f90",
    "pascal": "sample.pas",
    "verilog": "sample.v",
    "vhdl": "sample.vhdl",
    "raku": "sample.raku",
    "assembly": "sample.asm",
    "css": "sample.css",
    "html": "sample.html",
    "json": "sample.json",
    "yaml": "sample.yaml",
    "xml": "sample.xml",
    "markdown": "sample.md",
    "restructuredtext": "sample.rst",
    "latex": "sample.tex",
}


def pack_languages() -> tuple[str, ...]:
    """Return every language name the pinned tree-sitter-language-pack exposes."""
    from tree_sitter_language_pack import SupportedLanguage

    return tuple(sorted(typing.get_args(SupportedLanguage)))


def load_language(name: str) -> tuple[str, str | None]:
    """Attempt to load a pack grammar and parse a trivial input.

    Returns ``(LOADS, None)`` on success or ``(FAILS_TO_LOAD, error)`` with the
    captured error string (the C#/ABI-15 failure class).
    """
    from tree_sitter import Parser
    from tree_sitter_language_pack import get_language

    try:
        language = get_language(name)  # type: ignore[arg-type]
        parser = Parser(language)
        tree = parser.parse(b"a")
        if tree.root_node is None:  # pragma: no cover - defensive
            return FAILS_TO_LOAD, "parse returned no root node"
    except Exception as exc:  # noqa: BLE001 - we want to record any failure
        return FAILS_TO_LOAD, f"{type(exc).__name__}: {exc}"
    return LOADS, None


def _extraction_source(language: str) -> Path:
    """Return the repo-relative path used to extraction-test a language."""
    if language in GOLDEN_LANGUAGES:
        return GOLDEN_REPOS_ROOT / language
    return SAMPLES_ROOT / SAMPLE_LANGUAGES[language]


def extraction_probe(language: str) -> dict[str, Any]:
    """Run extraction for one language and return its classification record.

    Classifies by distinct-kind count; ``status=error`` (no parser resolved)
    becomes ``EXTRACTION_GAP`` -- chunker advertises the extension but cannot
    back it, which the IR records as a ``boundary.parse_error`` diagnostic.
    """
    from chunker.boundary import extract_boundary_ir

    path = _extraction_source(language)
    ir = extract_boundary_ir(path, language)
    kinds = sorted({node["kind"] for node in ir["nodes"]})
    files = ir["files"]
    status = files[0]["status"] if files else None

    if status == "error":
        classification = EXTRACTION_GAP
    elif len(kinds) >= 2:
        classification = RICH
    elif len(kinds) == 1:
        classification = SPARSE
    else:
        classification = EMPTY

    return {
        "classification": classification,
        "node_count": len(ir["nodes"]),
        "kinds": kinds,
        "status": status,
    }


def compute_coverage() -> dict[str, Any]:
    """Compute the full per-language coverage record across the pinned pack.

    The returned mapping is the canonical, byte-stable coverage artifact: the
    committed ``docs/language-coverage.json`` is exactly this structure, and the
    smoke-tier test diffs a live recomputation against it (drift in either
    direction -- a language that stops loading, or one that newly gains/loses an
    extraction surface -- fails the gate).
    """
    from importlib import metadata

    languages: dict[str, Any] = {}
    pack = pack_languages()

    extraction_targets = set(GOLDEN_LANGUAGES) | set(SAMPLE_LANGUAGES)

    for name in pack:
        load_status, load_error = load_language(name)
        record: dict[str, Any] = {"load": load_status}
        if load_error is not None:
            record["load_error"] = load_error

        if name in extraction_targets and load_status == LOADS:
            probe = extraction_probe(name)
            record["extraction"] = probe["classification"]
            record["node_count"] = probe["node_count"]
            record["kinds"] = probe["kinds"]
            record["sample"] = (
                "golden-fixture"
                if name in GOLDEN_LANGUAGES
                else (SAMPLES_ROOT / SAMPLE_LANGUAGES[name]).as_posix()
            )
        else:
            record["extraction"] = LOAD_ONLY

        languages[name] = record

    # Extraction targets chunker advertises (via EXTENSION_MAP) under a name the
    # pack does not enumerate at all -- e.g. ``assembly``/``restructuredtext``
    # (the pack ships these as ``asm``/``rst``) and ``cobol``/``fsharp``/``raku``
    # (no pack grammar under any name). A user dropping the matching file gets
    # ``status=error`` + 0 nodes; the IR records ``boundary.parse_error``. These
    # are advertised-but-broken, the most damning coverage class, and would be
    # invisible if we only iterated the pack. Record them explicitly.
    for name in sorted(extraction_targets - set(pack)):
        probe = extraction_probe(name)
        languages[name] = {
            "load": FAILS_TO_LOAD,
            "load_error": "no pack grammar enumerated under this name",
            "extraction": EXTRACTION_GAP,
            "node_count": probe["node_count"],
            "kinds": probe["kinds"],
            "sample": (SAMPLES_ROOT / SAMPLE_LANGUAGES[name]).as_posix(),
        }

    # Summary counts -- the honest headline numbers. ``pack_total`` /
    # ``loads`` / ``fails_to_load`` are scoped to the enumerable pack; the
    # advertised-but-broken extraction-gap names are counted under extraction.
    load_ok = sum(
        1 for name, r in languages.items() if name in pack and r["load"] == LOADS
    )
    by_extraction: dict[str, int] = {}
    for r in languages.values():
        by_extraction[r["extraction"]] = by_extraction.get(r["extraction"], 0) + 1

    return {
        "pins": {
            "tree_sitter": metadata.version("tree_sitter"),
            "tree_sitter_language_pack": metadata.version("tree-sitter-language-pack"),
        },
        "summary": {
            "pack_total": len(pack),
            "loads": load_ok,
            "fails_to_load": len(pack) - load_ok,
            "advertised_no_pack_grammar": len(extraction_targets - set(pack)),
            "extraction": by_extraction,
        },
        "languages": languages,
    }
