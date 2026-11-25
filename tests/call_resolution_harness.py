"""Identity harness for opt-in call resolution (treesitter-chunker#682).

Plan ``plans/detailed-scoped-call-resolution-682.md`` section 11.1. The
comparators take an off-mode and an on-mode document and return every
violation, tagged with the plan's check number:

1. ``symbol_lookup`` (keys include ``#N``), ``symbols``, ``call_facts`` and
   non-call relationships are equal, in order.
2. Call relationships keep their length, order and ``call_site_id``; only
   ``to``, ``resolution``, ``candidates``, ``is_internal`` and the two
   provenance keys may differ, and the keys appear only on changed edges.
3. Narrowing: on-candidates are a subset of off-candidates; an edge that is
   not ambiguous off is identical on; an ambiguous edge keeps two or more
   candidates and ``to == reference``; a resolved edge has
   ``candidates == [to]``, ``to`` in the off set, ``is_internal`` true and a
   binding rule in ``call_rules``. A proven JS/TS imports-mode alias can replace
   the entire off set with its single target, marked ``t2.import_alias``.
4. ``metadata`` is equal except ``call_resolution``.
5. Boundary ``nodes``, ``files``, ``diagnostics``, ``source`` and
   ``schema_version`` are byte-identical.
6. The edge ``id`` set is the same; non-call edges are byte-identical; call
   edges differ only in ``target``, ``resolution``, ``candidates``,
   ``metadata.is_internal`` and the two provenance keys; ``call_site_id ==
   id``.
7. Boundary narrowing invariants (B2), including the provenance keys of
   changed edges.
8. Resolution counters match the emitted edges; other metrics stay equal; ``run.options`` is equal except
   ``call_resolution``.
9. ``call_resolution="name"`` is byte-identical to omitting the argument.
10. Off-mode output equals the PR 0 baseline: see
    :func:`off_baseline_violations` (and ``test_call_resolution_today.py``,
    which checks every run).
12. On-mode cold, warm-incremental and repeated cold runs are byte-identical.

Check 11 (Boundary goldens, never regenerated) is
``tests/test_boundary_ir_golden_snapshots.py``; check 13 is
``tests/test_call_resolution_cache.py``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from chunker.call_resolution.modules import JS_EXTENSION_LANGUAGES
from chunker.call_resolution.engine import (
    BINDING_RULE_IDS,
    GROUP_RULE_IDS,
    KNOWN_RULE_IDS,
    RULE_IMPORT_ALIAS,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "call_resolution"
BOUNDARY_REPOS = ROOT / "tests" / "fixtures" / "boundary_ir" / "repos"
SCOPE_FACTS_DIGESTS = FIXTURES / "scope_facts_digests.json"
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_call_resolution_off_baseline.py"

# The on modes at this head: Tier 1, and Tier 1 plus Tier 2 (PR 5).
ON_MODES = ("structural", "imports")
RESOLUTION_MODES = ("strict", "permissive")
PROVENANCE_KEYS = ("call_resolution", "call_rules")
CALL_MUTABLE_FIELDS = ("to", "resolution", "candidates", "is_internal", "provenance")
EDGE_MUTABLE_FIELDS = ("target", "resolution", "candidates", "metadata", "provenance")


def load_capture() -> ModuleType:
    """The PR 0 baseline capture script, as a module."""
    name = "capture_call_resolution_off_baseline"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, CAPTURE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class HarnessRun:
    """One extraction root the harness compares off and on."""

    run_id: str
    path: Path
    language: str | None


def harness_runs() -> list[HarnessRun]:
    """Every fixture run (Greenfield, probe, authored, controls) and every
    ``tests/fixtures/boundary_ir/repos/*`` repository."""
    capture = load_capture()
    runs = [
        HarnessRun(run.run_id, run.path, run.language)
        for run in capture.discover_runs()
    ]
    runs.extend(
        HarnessRun(f"boundary_ir/{repo.name}", repo, None)
        for repo in sorted(BOUNDARY_REPOS.iterdir())
        if repo.is_dir()
    )
    return runs


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class Violation:
    check: int
    message: str


def failed_checks(violations: Iterable[Violation]) -> set[int]:
    return {violation.check for violation in violations}


# ---------------------------------------------------------------------------
# Symbol graph (checks 1-4)


def _calls(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in graph["relationships"] if edge.get("type") == "calls"]


def _non_calls(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in graph["relationships"] if edge.get("type") != "calls"]


def _without(record: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    dropped = set(keys)
    return {key: value for key, value in record.items() if key not in dropped}


def _provenance_violations(
    off: dict[str, Any],
    on: dict[str, Any],
    mode: str,
    changed: bool,
    label: str,
    *,
    beyond_check: int,
    keys_check: int,
) -> list[Violation]:
    """Provenance may differ only by the two keys, and only on changed edges.

    A difference beyond the two keys is reported as ``beyond_check``; a
    missing, malformed or misplaced key as ``keys_check``.
    """
    off_provenance = off.get("provenance")
    on_provenance = on.get("provenance")
    if not isinstance(off_provenance, dict) or not isinstance(on_provenance, dict):
        return [Violation(beyond_check, f"{label}: provenance is not an object")]
    found: list[Violation] = []
    if any(key in off_provenance for key in PROVENANCE_KEYS):
        found.append(Violation(keys_check, f"{label}: off-mode edge has the keys"))
    if _without(on_provenance, PROVENANCE_KEYS) != _without(
        off_provenance, PROVENANCE_KEYS
    ):
        found.append(
            Violation(beyond_check, f"{label}: provenance differs beyond the two keys")
        )
    if not changed:
        if any(key in on_provenance for key in PROVENANCE_KEYS):
            found.append(Violation(keys_check, f"{label}: unchanged edge has the keys"))
        return found
    if on_provenance.get("call_resolution") != mode:
        found.append(Violation(keys_check, f"{label}: call_resolution is not {mode!r}"))
    rules = on_provenance.get("call_rules")
    if (
        not isinstance(rules, list)
        or not rules
        or any(rule not in KNOWN_RULE_IDS for rule in rules)
    ):
        found.append(
            Violation(keys_check, f"{label}: call_rules {rules!r} is not valid")
        )
    return found


def symbol_graph_violations(
    off: dict[str, Any], on: dict[str, Any], mode: str
) -> list[Violation]:
    """Checks 1-4 for one (off, on) symbol-graph pair."""
    found: list[Violation] = []
    # Check 1.
    if list(off["symbol_lookup"].items()) != list(on["symbol_lookup"].items()):
        found.append(Violation(1, "symbol_lookup differs"))
    for key in ("symbols", "call_facts"):
        if off.get(key) != on.get(key):
            found.append(Violation(1, f"{key} differs"))
    if _non_calls(off) != _non_calls(on):
        found.append(Violation(1, "non-call relationships differ"))
    if set(off) != set(on):
        found.append(Violation(1, "top-level keys differ"))
    if off.get("errors") != on.get("errors"):
        found.append(Violation(4, "errors differ"))
    # Check 4.
    off_metadata = dict(off.get("metadata", {}))
    on_metadata = dict(on.get("metadata", {}))
    if "call_resolution" in off_metadata:
        found.append(Violation(4, "off-mode metadata has call_resolution"))
    if on_metadata.pop("call_resolution", None) != mode:
        found.append(Violation(4, f"metadata.call_resolution is not {mode!r}"))
    if off_metadata != on_metadata:
        found.append(Violation(4, "metadata differs beyond call_resolution"))
    # Checks 2 and 3.
    off_calls, on_calls = _calls(off), _calls(on)
    if [edge.get("call_site_id") for edge in off_calls] != [
        edge.get("call_site_id") for edge in on_calls
    ]:
        found.append(Violation(2, "call relationships differ in length, order or id"))
        return found
    symbol_ids = on["symbol_lookup"].keys()
    for off_edge, on_edge in zip(off_calls, on_calls, strict=True):
        label = str(off_edge.get("call_site_id"))
        if _without(off_edge, CALL_MUTABLE_FIELDS) != _without(
            on_edge, CALL_MUTABLE_FIELDS
        ):
            found.append(Violation(2, f"{label}: immutable fields differ"))
        changed = _without(off_edge, ("provenance",)) != _without(
            on_edge, ("provenance",)
        )
        found.extend(
            _provenance_violations(
                off_edge,
                on_edge,
                mode,
                changed,
                label,
                beyond_check=2,
                keys_check=2,
            )
        )
        rules = (on_edge.get("provenance") or {}).get("call_rules")
        if isinstance(rules, list) and RULE_IMPORT_ALIAS in rules:
            found.extend(
                _alias_violations(off_edge, on_edge, mode, symbol_ids, 3, label)
            )
        else:
            found.extend(_narrowing_violations(off_edge, on_edge, label))
    return found


def _alias_violations(
    off: dict[str, Any],
    on: dict[str, Any],
    mode: str,
    ids: Iterable[str],
    check: int,
    label: str,
) -> list[Violation]:
    """The sole exception to the remove-only contract, on both graph surfaces."""
    target = on["to"] if "to" in on else on["target"]
    internal = on.get("is_internal", on.get("metadata", {}).get("is_internal"))
    rules = on["provenance"]["call_rules"]
    if (
        mode != "imports"
        or Path(off["file"]).suffix.lower() not in JS_EXTENSION_LANGUAGES
        or rules[0] != RULE_IMPORT_ALIAS
        or not set(rules[1:]) <= GROUP_RULE_IDS
        or on["resolution"] != "resolved"
        or on["candidates"] != [target]
        or target in off["candidates"]
        or target not in ids
        or internal is not True
    ):
        return [Violation(check, f"{label}: invalid alias substitution")]
    return []


def _narrowing_violations(
    off: dict[str, Any], on: dict[str, Any], label: str
) -> list[Violation]:
    """Check 3 for one call relationship."""
    found: list[Violation] = []
    off_candidates = list(off.get("candidates") or [])
    on_candidates = list(on.get("candidates") or [])
    if not set(on_candidates) <= set(off_candidates):
        found.append(Violation(3, f"{label}: candidate outside the off set"))
    if off.get("resolution") != "ambiguous":
        if on != off:
            found.append(Violation(3, f"{label}: edge not ambiguous off changed"))
        return found
    resolution = on.get("resolution")
    if resolution == "ambiguous":
        if len(on_candidates) < 2 or len(set(on_candidates)) != len(on_candidates):
            found.append(Violation(3, f"{label}: ambiguous with < 2 candidates"))
        if on.get("to") != on.get("reference") or on.get("is_internal"):
            found.append(Violation(3, f"{label}: ambiguous edge has a target"))
    elif resolution == "resolved":
        rules = (on.get("provenance") or {}).get("call_rules") or []
        if (
            on_candidates != [on.get("to")]
            or on.get("to") not in off_candidates
            or on.get("is_internal") is not True
        ):
            found.append(Violation(3, f"{label}: resolved edge has the wrong shape"))
        if not BINDING_RULE_IDS & set(rules):
            found.append(Violation(3, f"{label}: resolved without a binding rule"))
    else:
        found.append(Violation(3, f"{label}: ambiguous edge became {resolution!r}"))
    return found


# ---------------------------------------------------------------------------
# Boundary IR (checks 5-8)


def _edges_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(edge["id"]): edge for edge in document["edges"]}


def _is_syntax_call(edge: dict[str, Any]) -> bool:
    return (
        edge.get("type") == "calls"
        and (edge.get("provenance") or {}).get("source") == "syntax"
    )


def boundary_violations(
    off: dict[str, Any], on: dict[str, Any], mode: str
) -> list[Violation]:
    """Checks 5-8 for one (off, on) Boundary IR pair."""
    found: list[Violation] = []
    # Check 5.
    for key in ("nodes", "files", "diagnostics", "source", "schema_version"):
        if canonical(off.get(key)) != canonical(on.get(key)):
            found.append(Violation(5, f"{key} differs"))
    # Check 8.
    off_metrics, on_metrics = dict(off["metrics"]), dict(on["metrics"])
    for document, metrics in ((off, off_metrics), (on, on_metrics)):
        counts = Counter(edge["resolution"] for edge in document["edges"])
        for status in ("unresolved", "ambiguous", "resolved"):
            if metrics.pop(f"{status}_edges") != counts[status]:
                found.append(Violation(8, f"wrong {status} edge count"))
    if off_metrics != on_metrics:
        found.append(Violation(8, "metrics differ beyond the resolution counts"))
    off_options = dict(off["run"]["options"])
    on_options = dict(on["run"]["options"])
    if "call_resolution" in off_options:
        found.append(Violation(8, "off-mode run.options has call_resolution"))
    if on_options.pop("call_resolution", None) != mode:
        found.append(Violation(8, f"run.options.call_resolution is not {mode!r}"))
    if off_options != on_options:
        found.append(Violation(8, "run.options differ beyond call_resolution"))
    if _without(off["run"], ("options",)) != _without(on["run"], ("options",)):
        found.append(Violation(8, "run differs beyond options"))
    if set(off) != set(on):
        found.append(Violation(5, "top-level keys differ"))
    # Checks 6 and 7.
    off_edges, on_edges = _edges_by_id(off), _edges_by_id(on)
    if set(off_edges) != set(on_edges) or len(off["edges"]) != len(on["edges"]):
        found.append(Violation(6, "edge id sets differ"))
    node_ids = {node["id"] for node in on["nodes"]}
    for edge_id in sorted(set(off_edges) & set(on_edges)):
        off_edge, on_edge = off_edges[edge_id], on_edges[edge_id]
        if not _is_syntax_call(off_edge):
            if canonical(off_edge) != canonical(on_edge):
                found.append(Violation(6, f"{edge_id}: non-call edge differs"))
            continue
        found.extend(_call_edge_violations(off_edge, on_edge, mode, edge_id, node_ids))
    for document in (off, on):
        for edge in document["edges"]:
            if not _is_syntax_call(edge):
                continue
            if edge.get("call_site_id") != edge.get("id"):
                found.append(Violation(6, f"{edge.get('id')}: call_site_id != id"))
            candidates = edge.get("candidates") or []
            if candidates != sorted(set(candidates)):
                found.append(Violation(7, f"{edge.get('id')}: candidates unsorted"))
            if edge.get("resolution") == "ambiguous" and edge.get("target") != edge.get(
                "reference"
            ):
                found.append(Violation(7, f"{edge.get('id')}: ambiguous target"))
    return found


def _call_edge_violations(
    off: dict[str, Any], on: dict[str, Any], mode: str, label: str, node_ids: set[str]
) -> list[Violation]:
    found: list[Violation] = []
    if _without(off, EDGE_MUTABLE_FIELDS) != _without(on, EDGE_MUTABLE_FIELDS):
        found.append(Violation(6, f"{label}: immutable fields differ"))
    off_metadata = dict(off.get("metadata") or {})
    on_metadata = dict(on.get("metadata") or {})
    off_metadata.pop("is_internal", None)
    on_metadata.pop("is_internal", None)
    if off_metadata != on_metadata:
        found.append(Violation(6, f"{label}: metadata differs beyond is_internal"))
    changed = _without(off, ("provenance",)) != _without(on, ("provenance",))
    found.extend(
        _provenance_violations(
            off, on, mode, changed, label, beyond_check=6, keys_check=7
        )
    )
    rules = (on.get("provenance") or {}).get("call_rules")
    if isinstance(rules, list) and RULE_IMPORT_ALIAS in rules:
        return found + _alias_violations(off, on, mode, node_ids, 7, label)
    off_candidates = list(off.get("candidates") or [])
    on_candidates = list(on.get("candidates") or [])
    if not set(on_candidates) <= set(off_candidates):
        found.append(Violation(7, f"{label}: candidate outside the off set"))
    if off.get("resolution") != "ambiguous":
        if canonical(off) != canonical(on):
            found.append(Violation(7, f"{label}: edge not ambiguous off changed"))
        return found
    is_internal = (on.get("metadata") or {}).get("is_internal")
    resolution = on.get("resolution")
    if resolution == "ambiguous":
        if len(on_candidates) < 2:
            found.append(Violation(7, f"{label}: ambiguous with < 2 candidates"))
        if on.get("target") != on.get("reference") or is_internal is not False:
            found.append(Violation(7, f"{label}: ambiguous edge has a target"))
    elif resolution == "resolved":
        rules = (on.get("provenance") or {}).get("call_rules") or []
        if (
            on_candidates != [on.get("target")]
            or on.get("target") not in off_candidates
            or is_internal is not True
        ):
            found.append(Violation(7, f"{label}: resolved edge has the wrong shape"))
        if not BINDING_RULE_IDS & set(rules):
            found.append(Violation(7, f"{label}: resolved without a binding rule"))
    else:
        found.append(Violation(7, f"{label}: ambiguous edge became {resolution!r}"))
    return found


# ---------------------------------------------------------------------------
# Off mode equals today (checks 9 and 10) and determinism (check 12)


def name_equals_omitted_violations(
    omitted: dict[str, Any], named: dict[str, Any]
) -> list[Violation]:
    """Check 9."""
    if canonical(omitted) != canonical(named):
        return [Violation(9, "call_resolution='name' differs from omitting it")]
    return []


def off_baseline_violations(
    run_id: str, mode: str, graph: dict[str, Any]
) -> list[Violation]:
    """Check 10: an off-mode symbol graph equals its committed baseline bytes."""
    capture = load_capture()
    committed = (capture.BASELINE / run_id / f"symbol_graph.{mode}.json").read_bytes()
    if capture.canonical_json(graph) != committed:
        return [Violation(10, f"{run_id}: off-mode output differs from the baseline")]
    return []


def determinism_violations(documents: dict[str, dict[str, Any]]) -> list[Violation]:
    """Check 12: every on-mode document of one run is byte-identical."""
    rendered = {name: canonical(document) for name, document in documents.items()}
    first = next(iter(rendered.values()))
    return [
        Violation(12, f"{name} differs from the first on-mode run")
        for name, text in rendered.items()
        if text != first
    ]


# ---------------------------------------------------------------------------
# Extraction


def symbol_graphs(
    run: HarnessRun, mode: str, resolution_mode: str = "permissive"
) -> tuple[dict[str, Any], dict[str, Any]]:
    from chunker.symbol_graph import extract_symbol_graph

    off = extract_symbol_graph(run.path, run.language, resolution_mode=resolution_mode)
    on = extract_symbol_graph(
        run.path,
        run.language,
        resolution_mode=resolution_mode,
        call_resolution=mode,
    )
    return off, on


def boundary_documents(
    run: HarnessRun, mode: str, resolution_mode: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    from chunker.boundary import extract_boundary_ir

    off = extract_boundary_ir(run.path, run.language, resolution_mode=resolution_mode)
    on = extract_boundary_ir(
        run.path,
        run.language,
        resolution_mode=resolution_mode,
        call_resolution=mode,
    )
    return off, on


def on_mode_documents(
    run: HarnessRun, mode: str, resolution_mode: str
) -> dict[str, dict[str, Any]]:
    """Cold, repeated cold, incremental cold and incremental warm on-mode runs."""
    from chunker.boundary import extract_boundary_ir

    def extract(**kwargs: Any) -> dict[str, Any]:
        return extract_boundary_ir(
            run.path,
            run.language,
            resolution_mode=resolution_mode,
            call_resolution=mode,
            **kwargs,
        )

    documents = {"cold": extract(), "cold again": extract()}
    with tempfile.TemporaryDirectory(prefix="call-resolution-harness-") as tmp:
        cache_dir = Path(tmp) / "cache"
        documents["incremental cold"] = extract(incremental=True, cache_dir=cache_dir)
        documents["incremental warm"] = extract(incremental=True, cache_dir=cache_dir)
    return documents


# ---------------------------------------------------------------------------
# Mutations (section 11.3)

Mutation = Callable[[dict[str, Any]], None]


def mutated(document: dict[str, Any], mutation: Mutation) -> dict[str, Any]:
    copied = copy.deepcopy(document)
    mutation(copied)
    return copied


def first(
    records: Iterable[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    for record in records:
        if predicate(record):
            return record
    msg = "no record matches the mutation's precondition"
    raise LookupError(msg)


# ---------------------------------------------------------------------------
# Scope-fact digests (section 4.6)


def fixture_scope_facts() -> list[tuple[str, dict[str, Any]]]:
    """``(run_id, on-mode facts)`` for every analyzed fixture file."""
    from chunker.call_resolution.facts import ANALYZED_LANGUAGES
    from chunker.symbol_graph import collect_source_files, extract_symbol_facts_for_file

    capture = load_capture()
    found: list[tuple[str, dict[str, Any]]] = []
    for run in capture.discover_runs():
        for file_path in collect_source_files(run.path, run.language):
            facts = extract_symbol_facts_for_file(
                file_path, run.path, run.language, call_resolution="structural"
            )
            if facts["language"] in ANALYZED_LANGUAGES:
                found.append((run.run_id, facts))
    return found


def scope_fact_digests() -> dict[str, dict[str, Any]]:
    """Per family, the fact version and a digest of each fixture file's facts.

    Keys are ``<run_id>:<display path>``; a file in two runs (the probe's two
    roots) has different facts per root.
    """
    import hashlib

    from chunker.call_resolution.engine import language_family
    from chunker.call_resolution.facts import CALL_RESOLUTION_FACT_VERSIONS

    digests: dict[str, dict[str, Any]] = {
        family: {"version": version, "files": {}}
        for family, version in sorted(CALL_RESOLUTION_FACT_VERSIONS.items())
    }
    for run_id, facts in fixture_scope_facts():
        family = language_family(facts["language"])
        assert family is not None
        data = canonical(facts["scope_facts"]).encode("utf-8")
        digests[family]["files"][f"{run_id}:{facts['path']}"] = hashlib.sha256(
            data
        ).hexdigest()
    for entry in digests.values():
        entry["files"] = dict(sorted(entry["files"].items()))
    return digests


def write_scope_fact_digests() -> None:
    capture = load_capture()
    SCOPE_FACTS_DIGESTS.write_bytes(capture.canonical_json(scope_fact_digests()))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if sys.argv[1:] != ["--write-scope-fact-digests"]:
        raise SystemExit(
            "usage: python -m tests.call_resolution_harness --write-scope-fact-digests"
        )
    write_scope_fact_digests()
    print(f"wrote {SCOPE_FACTS_DIGESTS.relative_to(ROOT).as_posix()}")
