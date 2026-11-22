"""Identity stability for opt-in call resolution (treesitter-chunker#682).

Plan section 11.1, run over every fixture tree and every
``tests/fixtures/boundary_ir/repos/*`` repository. Parametrized per run and
mode, because the smoke lane runs with ``-n 2 --timeout=60``. Section 11.3's
mutation self-tests prove each comparator check fails when it should.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from tests import call_resolution_harness as harness
from tests.call_resolution_harness import Violation, failed_checks

RUNS = harness.harness_runs()
RUN_IDS = [run.run_id for run in RUNS]
RUNS_BY_ID = {run.run_id: run for run in RUNS}
# Controls (plan 10.5 and gate 7): identical on and off except the recorded
# mode, and no edge carries the new keys.
CONTROL_TREES = (
    "clo-go",
    "clo-kotlin",
    "clo-rust",
    "ctl-c",
    "ctl-cpp",
    "ctl-csharp",
    "ctl-go",
    "ctl-java",
    "ctl-kotlin",
    "ctl-rust",
    "rt-cpp",
    "rt-go",
    "rt-java",
    "rt-kotlin",
    "rt-rust",
)
NO_CALL_CONTROLS = ("ctl-csharp", "ctl-java", "ctl-kotlin")


def _describe(violations: list[Violation]) -> str:
    return "\n".join(f"[{item.check}] {item.message}" for item in violations[:20])


@pytest.mark.parametrize("mode", harness.ON_MODES)
@pytest.mark.parametrize("run_id", RUN_IDS)
def test_symbol_graph_identity(run_id: str, mode: str) -> None:
    """Checks 1-4 and 9 on the symbol graph."""
    from chunker.symbol_graph import extract_symbol_graph

    run = RUNS_BY_ID[run_id]
    off, on = harness.symbol_graphs(run, mode)
    named = extract_symbol_graph(run.path, run.language, call_resolution="name")
    violations = harness.symbol_graph_violations(off, on, mode)
    violations += harness.name_equals_omitted_violations(off, named)
    assert violations == [], _describe(violations)


@pytest.mark.parametrize("resolution_mode", harness.RESOLUTION_MODES)
@pytest.mark.parametrize("mode", harness.ON_MODES)
@pytest.mark.parametrize("run_id", RUN_IDS)
def test_boundary_identity(run_id: str, mode: str, resolution_mode: str) -> None:
    """Checks 5-8 on Boundary IR, for both ``resolution_mode`` values."""
    run = RUNS_BY_ID[run_id]
    off, on = harness.boundary_documents(run, mode, resolution_mode)
    violations = harness.boundary_violations(off, on, mode)
    assert violations == [], _describe(violations)


@pytest.mark.parametrize("resolution_mode", harness.RESOLUTION_MODES)
@pytest.mark.parametrize("mode", harness.ON_MODES)
@pytest.mark.parametrize("run_id", RUN_IDS)
def test_on_mode_is_deterministic(run_id: str, mode: str, resolution_mode: str) -> None:
    """Check 12: cold, repeated cold and cold/warm incremental runs agree."""
    documents = harness.on_mode_documents(RUNS_BY_ID[run_id], mode, resolution_mode)
    violations = harness.determinism_violations(documents)
    assert violations == [], _describe(violations)


def test_harness_covers_every_fixture_and_boundary_repo() -> None:
    capture = harness.load_capture()
    fixture_runs = {run.run_id for run in capture.discover_runs()}
    repos = {
        f"boundary_ir/{path.name}"
        for path in harness.BOUNDARY_REPOS.iterdir()
        if path.is_dir()
    }
    assert set(RUN_IDS) == fixture_runs | repos
    assert len(RUN_IDS) == len(set(RUN_IDS))
    assert {"boundary_ir/go", "boundary_ir/python", "boundary_ir/typescript"} <= repos


@pytest.mark.parametrize("mode", harness.ON_MODES)
@pytest.mark.parametrize("tree", CONTROL_TREES)
def test_controls_are_identical_except_the_recorded_mode(tree: str, mode: str) -> None:
    """Gate 7: controls change only ``call_resolution`` metadata/options."""
    run = RUNS_BY_ID[f"{tree}/default"]
    off, on = harness.symbol_graphs(run, mode)
    on_metadata = dict(on["metadata"])
    assert on_metadata.pop("call_resolution") == mode
    assert {**on, "metadata": on_metadata} == off
    for resolution_mode in harness.RESOLUTION_MODES:
        boundary_off, boundary_on = harness.boundary_documents(
            run, mode, resolution_mode
        )
        options = dict(boundary_on["run"]["options"])
        assert options.pop("call_resolution") == mode
        rebuilt = copy.deepcopy(boundary_on)
        rebuilt["run"]["options"] = options
        assert harness.canonical(rebuilt) == harness.canonical(boundary_off)
        for edge in boundary_on["edges"]:
            assert not set(harness.PROVENANCE_KEYS) & set(edge["provenance"])
    if tree in NO_CALL_CONTROLS:
        assert not [edge for edge in on["relationships"] if edge["type"] == "calls"]


# ---------------------------------------------------------------------------
# Mutation proofs (section 11.3)

_PAIRS: dict[str, Any] = {}


def _pair(run_id: str, mode: str = "structural") -> dict[str, Any]:
    """A real (off, on) pair, for the symbol graph and strict Boundary IR."""
    key = f"{run_id}@{mode}"
    if key not in _PAIRS:
        run = RUNS_BY_ID[run_id]
        off, on = harness.symbol_graphs(run, mode)
        boundary_off, boundary_on = harness.boundary_documents(run, mode, "strict")
        _PAIRS[key] = {
            "graph": (off, on),
            "boundary": (boundary_off, boundary_on),
        }
    return _PAIRS[key]


def _calls(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in graph["relationships"] if edge["type"] == "calls"]


def _syntax_calls(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in document["edges"] if edge["type"] == "calls"]


def _with(resolution: str) -> Callable[[dict[str, Any]], bool]:
    return lambda edge: edge["resolution"] == resolution


# Symbol-graph mutations.


def _sg_change_definition_id(graph: dict[str, Any]) -> None:
    symbol = next(iter(graph["symbol_lookup"].values()))
    symbol["definition_id"] = "0" * 40


def _sg_swap_suffixes(graph: dict[str, Any]) -> None:
    lookup = graph["symbol_lookup"]
    suffixed = next(key for key in lookup if "#" in key)
    base = suffixed.split("#", 1)[0]
    lookup[base], lookup[suffixed] = lookup[suffixed], lookup[base]


def _sg_change_call_site_id(graph: dict[str, Any]) -> None:
    _calls(graph)[0]["call_site_id"] = "call:" + "0" * 40


def _sg_change_non_call(graph: dict[str, Any]) -> None:
    edge = harness.first(graph["relationships"], lambda edge: edge["type"] != "calls")
    edge["resolution"] = "unresolved" if edge["resolution"] != "unresolved" else "x"


def _sg_empty_ambiguous(graph: dict[str, Any]) -> None:
    harness.first(_calls(graph), _with("ambiguous"))["candidates"] = []


def _sg_add_candidate(graph: dict[str, Any]) -> None:
    harness.first(_calls(graph), _with("ambiguous"))["candidates"].append("f" * 40)


def _sg_retarget_resolved(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _with("resolved"))
    other = next(key for key in graph["symbol_lookup"] if key != edge["to"])
    edge["to"] = other
    edge["candidates"] = [other]


def _sg_change_unresolved(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _with("unresolved"))
    edge["reference"] += "_changed"


def _sg_reorder_calls(graph: dict[str, Any]) -> None:
    calls = _calls(graph)
    first_index = graph["relationships"].index(calls[0])
    second_index = graph["relationships"].index(calls[1])
    relationships = graph["relationships"]
    relationships[first_index], relationships[second_index] = (
        relationships[second_index],
        relationships[first_index],
    )


def _sg_drop_call(graph: dict[str, Any]) -> None:
    graph["relationships"].remove(_calls(graph)[-1])


def _sg_extra_provenance_key(graph: dict[str, Any]) -> None:
    _calls(graph)[0]["provenance"]["extra"] = "x"


def _resolve(edge: dict[str, Any], candidates: list[str], rules: list[str]) -> None:
    edge["resolution"] = "resolved"
    edge["to"] = candidates[0]
    edge["candidates"] = candidates
    edge["is_internal"] = True
    edge["provenance"] = {
        **edge["provenance"],
        "call_resolution": "structural",
        "call_rules": rules,
    }


def _sg_resolved_wrong_candidates(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _with("ambiguous"))
    _resolve(edge, list(edge["candidates"]), ["t1.lexical"])


def _sg_resolved_by_filter_only(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _with("ambiguous"))
    _resolve(edge, [edge["candidates"][0]], ["t1.kind"])


# Boundary mutations.


def _bir_change_definition_id(document: dict[str, Any]) -> None:
    harness.first(document["nodes"], lambda node: bool(node["definition_id"]))[
        "definition_id"
    ] = ("0" * 40)


def _bir_swap_suffixes(document: dict[str, Any]) -> None:
    nodes = {node["id"]: node for node in document["nodes"]}
    suffixed = next(key for key in nodes if "#" in key)
    base = suffixed.split("#", 1)[0]
    nodes[base]["id"], nodes[suffixed]["id"] = suffixed, base


def _bir_change_call_site_id(document: dict[str, Any]) -> None:
    edge = _syntax_calls(document)[0]
    edge["id"] = edge["call_site_id"] = "call:" + "0" * 40


def _bir_change_non_call(document: dict[str, Any]) -> None:
    edge = harness.first(document["edges"], lambda edge: edge["type"] != "calls")
    edge["target"] += "_changed"


def _bir_empty_ambiguous(document: dict[str, Any]) -> None:
    harness.first(_syntax_calls(document), _with("ambiguous"))["candidates"] = []


def _bir_add_candidate(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _with("ambiguous"))
    edge["candidates"] = sorted([*edge["candidates"], "f" * 40])


def _bir_retarget_resolved(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _with("resolved"))
    other = next(
        node["id"] for node in document["nodes"] if node["id"] != edge["target"]
    )
    edge["target"] = other
    edge["candidates"] = [other]


def _bir_change_unresolved(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _with("unresolved"))
    edge["metadata"]["is_internal"] = True


def _bir_drop_call(document: dict[str, Any]) -> None:
    document["edges"].remove(_syntax_calls(document)[-1])


def _bir_extra_provenance_key(document: dict[str, Any]) -> None:
    _syntax_calls(document)[0]["provenance"]["extra"] = "x"


def _bir_resolve(edge: dict[str, Any], candidates: list[str], rules: list[str]) -> None:
    edge["resolution"] = "resolved"
    edge["target"] = candidates[0]
    edge["candidates"] = candidates
    edge["metadata"]["is_internal"] = True
    edge["provenance"] = {
        **edge["provenance"],
        "call_resolution": "structural",
        "call_rules": rules,
    }


def _bir_resolved_wrong_candidates(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _with("ambiguous"))
    _bir_resolve(edge, list(edge["candidates"]), ["t1.lexical"])


def _bir_resolved_by_filter_only(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _with("ambiguous"))
    _bir_resolve(edge, [edge["candidates"][0]], ["t1.kind"])


SG = "graph"
BIR = "boundary"
# (mutation, real pair, representation, mutation function, checks that must fail)
MUTATIONS = [
    ("M1", "rt-pyrec/default", SG, _sg_change_definition_id, {1}),
    ("M1", "rt-pyrec/default", BIR, _bir_change_definition_id, {5}),
    ("M2", "rt-pyrec/default", SG, _sg_swap_suffixes, {1}),
    ("M2", "rt-pyrec/default", BIR, _bir_swap_suffixes, {5}),
    ("M3", "r9-py/default", SG, _sg_change_call_site_id, {2}),
    ("M3", "r9-py/default", BIR, _bir_change_call_site_id, {6}),
    ("M4", "r9-py/default", SG, _sg_change_non_call, {1}),
    ("M4", "r9-py/default", BIR, _bir_change_non_call, {6}),
    ("M5", "mixed-family/default", SG, _sg_empty_ambiguous, {3}),
    ("M5", "mixed-family/default", BIR, _bir_empty_ambiguous, {7}),
    ("M6", "mixed-family/default", SG, _sg_add_candidate, {3}),
    ("M6", "mixed-family/default", BIR, _bir_add_candidate, {7}),
    ("M7", "r9-py/default", SG, _sg_retarget_resolved, {3}),
    ("M7", "r9-py/default", BIR, _bir_retarget_resolved, {7}),
    ("M8", "r9-py/default", SG, _sg_change_unresolved, {3}),
    ("M8", "r9-py/default", BIR, _bir_change_unresolved, {7}),
    ("M9", "r9-py/default", SG, _sg_reorder_calls, {2}),
    ("M10", "r9-py/default", SG, _sg_drop_call, {2}),
    ("M10", "r9-py/default", BIR, _bir_drop_call, {6}),
    ("M11", "r9-py/default", SG, _sg_extra_provenance_key, {2}),
    ("M11", "r9-py/default", BIR, _bir_extra_provenance_key, {6}),
    ("M12", "mixed-family/default", SG, _sg_resolved_wrong_candidates, {3}),
    ("M12", "mixed-family/default", BIR, _bir_resolved_wrong_candidates, {7}),
    ("M14", "mixed-family/default", SG, _sg_resolved_by_filter_only, {3}),
]


def _is_tier2(edge: dict[str, Any]) -> bool:
    rules = (edge.get("provenance") or {}).get("call_rules") or []
    return bool({"t2.import", "t2.namespace"} & set(rules))


def _sg_tier2_mode_mismatch(graph: dict[str, Any]) -> None:
    harness.first(_calls(graph), _is_tier2)["provenance"][
        "call_resolution"
    ] = "structural"


def _bir_tier2_mode_mismatch(document: dict[str, Any]) -> None:
    harness.first(_syntax_calls(document), _is_tier2)["provenance"][
        "call_resolution"
    ] = "structural"


def _sg_tier2_without_binding_rule(graph: dict[str, Any]) -> None:
    harness.first(_calls(graph), _is_tier2)["provenance"]["call_rules"] = ["t1.family"]


def _bir_tier2_without_binding_rule(document: dict[str, Any]) -> None:
    harness.first(_syntax_calls(document), _is_tier2)["provenance"]["call_rules"] = [
        "t1.family"
    ]


def _sg_tier2_retarget(graph: dict[str, Any]) -> None:
    """Re-target a Tier 2 resolution to a symbol outside today's set (the
    file's own caller ``u``)."""
    edge = harness.first(_calls(graph), _is_tier2)
    other = edge["from"]
    edge["to"] = other
    edge["candidates"] = [other]


def _bir_tier2_retarget(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _is_tier2)
    other = edge["source"]
    edge["target"] = other
    edge["candidates"] = [other]


# Mutation proofs on real ``imports``-mode pairs (PR 5): a Tier 2 resolved
# edge (``t2.import`` in ts-barrel, ``t2.namespace`` in ts-namespace-import).
IMPORTS_MUTATIONS = [
    ("M3", "ts-barrel/default", SG, _sg_change_call_site_id, {2}),
    ("M3", "ts-barrel/default", BIR, _bir_change_call_site_id, {6}),
    ("M7", "ts-barrel/default", SG, _sg_tier2_retarget, {3}),
    ("M7", "ts-barrel/default", BIR, _bir_tier2_retarget, {7}),
    ("M7", "ts-namespace-import/default", SG, _sg_tier2_retarget, {3}),
    ("M7", "ts-namespace-import/default", BIR, _bir_tier2_retarget, {7}),
    ("M11", "ts-barrel/default", SG, _sg_extra_provenance_key, {2}),
    ("M11", "ts-barrel/default", BIR, _bir_extra_provenance_key, {6}),
    ("M14", "ts-barrel/default", SG, _sg_tier2_without_binding_rule, {3}),
    ("M14", "ts-barrel/default", BIR, _bir_tier2_without_binding_rule, {7}),
    ("M15", "ts-barrel/default", SG, _sg_tier2_mode_mismatch, {2}),
    ("M15", "ts-barrel/default", BIR, _bir_tier2_mode_mismatch, {7}),
]


@pytest.mark.parametrize("run_id", sorted({item[1] for item in IMPORTS_MUTATIONS}))
def test_imports_mutation_bases_pass_unmutated(run_id: str) -> None:
    pair = _pair(run_id, "imports")
    assert any(_is_tier2(edge) for edge in _calls(pair[SG][1]))
    assert harness.symbol_graph_violations(*pair[SG], "imports") == []
    assert harness.boundary_violations(*pair[BIR], "imports") == []


@pytest.mark.parametrize(
    ("name", "run_id", "representation", "mutation", "must_fail"),
    IMPORTS_MUTATIONS,
    ids=[f"{item[0]}-{item[1].split('/')[0]}-{item[2]}" for item in IMPORTS_MUTATIONS],
)
def test_imports_mutation_fails_its_checks(
    name: str,
    run_id: str,
    representation: str,
    mutation: harness.Mutation,
    must_fail: set[int],
) -> None:
    off, on = _pair(run_id, "imports")[representation]
    compare = (
        harness.symbol_graph_violations
        if representation == SG
        else harness.boundary_violations
    )
    violations = compare(off, harness.mutated(on, mutation), "imports")
    assert must_fail <= failed_checks(violations), (name, _describe(violations))


@pytest.mark.parametrize("run_id", sorted({item[1] for item in MUTATIONS}))
def test_mutation_bases_pass_unmutated(run_id: str) -> None:
    pair = _pair(run_id)
    assert harness.symbol_graph_violations(*pair[SG], "structural") == []
    assert harness.boundary_violations(*pair[BIR], "structural") == []


@pytest.mark.parametrize(
    ("name", "run_id", "representation", "mutation", "must_fail"),
    MUTATIONS,
    ids=[f"{item[0]}-{item[2]}" for item in MUTATIONS],
)
def test_mutation_fails_its_checks(
    name: str,
    run_id: str,
    representation: str,
    mutation: harness.Mutation,
    must_fail: set[int],
) -> None:
    off, on = _pair(run_id)[representation]
    compare = (
        harness.symbol_graph_violations
        if representation == SG
        else harness.boundary_violations
    )
    violations = compare(off, harness.mutated(on, mutation), "structural")
    assert must_fail <= failed_checks(violations), (name, _describe(violations))


# Isolated variants (panel C1): each breaks exactly one rule, so the check
# cannot pass for an incidental reason. The narrowed edge keeps valid
# provenance keys, so only the mutated property is wrong.


def _narrowed(edge: dict[str, Any]) -> bool:
    return "call_rules" in edge["provenance"]


def _sg_iso_change_definition_id(graph: dict[str, Any]) -> None:
    lookup = graph["symbol_lookup"]
    key = next(iter(lookup))
    lookup[key] = {**lookup[key], "definition_id": "0" * 40}


def _sg_iso_empty_narrowed(graph: dict[str, Any]) -> None:
    harness.first(_calls(graph), _narrowed)["candidates"] = []


def _bir_iso_empty_narrowed(document: dict[str, Any]) -> None:
    harness.first(_syntax_calls(document), _narrowed)["candidates"] = []


def _sg_iso_one_candidate(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _narrowed)
    edge["candidates"] = edge["candidates"][:1]


def _bir_iso_one_candidate(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _narrowed)
    edge["candidates"] = edge["candidates"][:1]


def _sg_iso_add_candidate(graph: dict[str, Any]) -> None:
    edge = harness.first(_calls(graph), _narrowed)
    edge["candidates"] = sorted([*edge["candidates"], "f" * 40])


def _bir_iso_add_candidate(document: dict[str, Any]) -> None:
    edge = harness.first(_syntax_calls(document), _narrowed)
    edge["candidates"] = sorted([*edge["candidates"], "f" * 40])


ISOLATED = [
    ("M1", "rt-pyrec/default", SG, _sg_iso_change_definition_id, 1),
    ("M3", "r9-py/default", BIR, _bir_change_call_site_id, 6),
    ("M5", "mixed-family/default", SG, _sg_iso_empty_narrowed, 3),
    ("M5", "mixed-family/default", BIR, _bir_iso_empty_narrowed, 7),
    ("M5", "mixed-family/default", SG, _sg_iso_one_candidate, 3),
    ("M5", "mixed-family/default", BIR, _bir_iso_one_candidate, 7),
    ("M6", "mixed-family/default", SG, _sg_iso_add_candidate, 3),
    ("M6", "mixed-family/default", BIR, _bir_iso_add_candidate, 7),
]


@pytest.mark.parametrize(
    ("name", "run_id", "representation", "mutation", "check"),
    ISOLATED,
    ids=[f"{item[0]}-{item[2]}-{item[3].__name__}" for item in ISOLATED],
)
def test_isolated_mutation_fails_exactly_one_rule(
    name: str,
    run_id: str,
    representation: str,
    mutation: harness.Mutation,
    check: int,
) -> None:
    off, on = _pair(run_id)[representation]
    compare = (
        harness.symbol_graph_violations
        if representation == SG
        else harness.boundary_violations
    )
    violations = compare(off, harness.mutated(on, mutation), "structural")
    assert len(violations) == 1, (name, _describe(violations))
    assert violations[0].check == check, (name, _describe(violations))


def test_mutation_m13_off_mode_byte_fails_check_10() -> None:
    from chunker.symbol_graph import extract_symbol_graph

    run = RUNS_BY_ID["r9-ts/default"]
    graph = extract_symbol_graph(run.path, run.language)
    assert harness.off_baseline_violations(run.run_id, "permissive", graph) == []

    def change_one_byte(document: dict[str, Any]) -> None:
        symbol = next(iter(document["symbol_lookup"].values()))
        symbol["name"] = symbol["name"][:-1] + chr(ord(symbol["name"][-1]) ^ 1)

    violations = harness.off_baseline_violations(
        run.run_id, "permissive", harness.mutated(graph, change_one_byte)
    )
    assert failed_checks(violations) == {10}


def test_mutation_table_covers_section_11_3() -> None:
    names = {item[0] for item in MUTATIONS} | {"M13"}
    assert names == {f"M{number}" for number in range(1, 15)}
    for name in ("M5", "M6", "M7", "M8", "M12"):
        assert {item[2] for item in MUTATIONS if item[0] == name} == {SG, BIR}


def test_determinism_and_name_checks_detect_differences() -> None:
    document = {"a": 1}
    assert failed_checks(
        harness.determinism_violations({"x": document, "y": {"a": 2}})
    ) == {12}
    assert failed_checks(
        harness.name_equals_omitted_violations(document, {"a": 2})
    ) == {9}
