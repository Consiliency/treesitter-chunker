"""Private GROUP controls: real native facts, real engine, independent oracles."""

import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

from filelock import FileLock, Timeout
import pytest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tools/governed_group.py"
FIXTURES = Path(__file__).parent / "fixtures/governed_group"
RECIPE = runpy.run_path(str(FIXTURES / "recipe.py"))
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())
ANCHOR = os.environ.get(
    "GROUP_TEST_SOURCE_COMMIT", "fe49736e89c436bff4de49992b68528f370ac598"
)
# GROUP_COMPUTE_TIMEOUT bounds each test's active GROUP work only
# (func_only=True). Waiting for the shared serialization lock happens in
# fixture setup and has its own, separately reported bound: GROUP_LOCK_WAIT.
# Under xdist, or several concurrent sessions sharing TMPDIR, queued tests
# previously spent the whole computation budget waiting for the lock
# (treesitter-chunker#514 N3).
GROUP_COMPUTE_TIMEOUT = 120
GROUP_LOCK_WAIT = 900
# Once one lock wait times out in this process, later GROUP tests fail at once
# instead of each waiting another GROUP_LOCK_WAIT, so persistent contention
# costs at most one full wait per worker.
_LOCK_EXHAUSTED = []
pytestmark = [
    pytest.mark.timeout(GROUP_COMPUTE_TIMEOUT, func_only=True),
    pytest.mark.skipif(
        sys.platform != "linux", reason="governed GROUP has a Linux validation tier"
    ),
]


def require(condition, name):
    if not condition:
        raise AssertionError(name)


@pytest.fixture(autouse=True)
def _one_group_process():
    # Smoke uses xdist. Its workers share this task-owned TMPDIR lock, so at
    # most one GROUP test computes at a time. The wait is bounded here, outside
    # the per-test computation timeout, and fails as a lock wait, not a GROUP
    # timeout.
    if _LOCK_EXHAUSTED:
        pytest.fail(
            "GROUP serialization lock wait already exhausted in this process",
            pytrace=False,
        )
    lock = FileLock(str(Path(tempfile.gettempdir()) / "chunker-group-tests.lock"))
    try:
        lock.acquire(timeout=GROUP_LOCK_WAIT)
    except Timeout:
        _LOCK_EXHAUSTED.append(True)
        pytest.fail(
            f"GROUP serialization lock not acquired within {GROUP_LOCK_WAIT}s",
            pytrace=False,
        )
    try:
        yield
    finally:
        lock.release()


def make_request(**kwargs):
    return RECIPE["request"](ROOT, ANCHOR, **kwargs)


def launch(tmp, request, *, expected=None, seed="1", raw=None, prelude=None):
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / "request.json"
    path.write_bytes(raw if raw is not None else RECIPE["canonical"](request))
    pins = expected or RECIPE["pins"](request)
    output = tmp / "output"
    argv = [str(DRIVER), "--request", str(path), "--output", str(output)]
    for key, argument in [
        ("request", "request"),
        ("source-binding", "source-binding"),
        ("profile", "profile"),
    ]:
        argv += ["--expected-" + argument + "-sha256", pins[key]]
    # This trusted test bootstrap also binds private mutation snapshots. The
    # product CLI accepts no import-root input and performs its own file joins.
    # A prelude is trusted test-only code run before the driver, never product
    # input; without one the command bytes are unchanged.
    bootstrap = (
        "import sys,runpy; "
        + ("" if prelude is None else "exec(" + repr(prelude) + "); ")
        + "sys.path.insert(0,"
        + repr(str(ROOT))
        + "); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    )
    command = [sys.executable, "-P"]
    if sys.flags.optimize:
        command.append("-O")
    command += ["-c", bootstrap, *argv]
    env = dict(os.environ, PYTHONHASHSEED=seed)
    env.pop("PYTHONPATH", None)
    cp = subprocess.run(command, capture_output=True, timeout=130, env=env)
    (tmp / "stdout.log").write_bytes(cp.stdout)
    (tmp / "stderr.log").write_bytes(cp.stderr)
    (tmp / "command.json").write_text(json.dumps(command))
    return cp, output


def accepted(cp, output):
    require(cp.returncode == 0, "GROUP_ACCEPTED:" + cp.stderr.decode(errors="replace"))
    proposal = json.loads((output / "proposal.json").read_bytes())
    require(
        proposal["proposal_digest"] == json.loads(cp.stdout)["proposal_digest"],
        "GROUP_RECEIPT",
    )
    return proposal


def rejected(cp, output, reason, exit_code=1):
    require(
        cp.returncode == exit_code and json.loads(cp.stderr)["reason"] == reason,
        "GROUP_REFUSAL:" + cp.stderr.decode(errors="replace"),
    )
    require(
        not cp.stdout and not (output / "proposal.json").exists(),
        "GROUP_REFUSAL_NO_PROPOSAL",
    )
    if reason != "group_compute":
        require(not output.exists(), "GROUP_REFUSAL_NO_OUTPUT")


def verify_proposal(request, proposal):
    expected = RECIPE["pins"](request)
    require(
        proposal["request_digest"] == expected["request"]
        and proposal["profile_digest"] == expected["profile"],
        "GROUP_PROFILE_BINDING",
    )
    require(proposal["approval"] == "proposal_only", "GROUP_NO_AUTHORITY")
    normalized = RECIPE["normalized"](request)
    require(
        proposal["relationships"] == normalized["graph"]["relationships"],
        "GROUP_FACT_ACCOUNTING",
    )
    ids = [g["id"] for g in proposal["groups"]]
    require(ids == sorted(ids), "GROUP_CANONICAL_ORDER")
    groups = {g["id"]: g for g in proposal["groups"]}
    for group in groups.values():
        parent = groups.get(group["parent_id"])
        value = {
            "policy_revision": request["policy"]["revision"],
            "parent_members": parent["members"] if parent else [],
            "heuristic_level": group["heuristic_level"],
            "members": sorted(group["members"]),
        }
        require(
            group["id"] == RECIPE["hashed"]("membership", value), "GROUP_MEMBERSHIP_ID"
        )
        require(group["metrics"]["cluster_id"] == group["id"], "GROUP_METRIC_ID")
        require(group["members"] == sorted(group["members"]), "GROUP_CANONICAL_ORDER")
    body = {k: v for k, v in proposal.items() if k != "proposal_digest"}
    require(
        proposal["proposal_digest"] == RECIPE["hashed"]("proposal", body),
        "GROUP_PROPOSAL_DIGEST",
    )


def test_literal_partitions_metrics_and_facts(tmp_path):
    for mode in ("declared_boundaries", "dependency_assisted"):
        request = make_request(mode=mode)
        cp, output = launch(tmp_path / mode, request)
        proposal = accepted(cp, output)
        verify_proposal(request, proposal)
        if mode == "declared_boundaries":
            members = sorted(g["members"] for g in proposal["groups"])
            require(members == EXPECTED["declared"], "GROUP_HARD_BOUNDARY")
            a = next(
                g
                for g in proposal["groups"]
                if g["members"] == ["a1", "a2", "a3", "a4"]
            )
            require(
                a["metrics"]["internal_edges"] == 2
                and a["metrics"]["density"] == 1 / 3,
                "GROUP_INDEPENDENT_METRICS",
            )
        else:
            members = sorted(
                g["members"]
                for g in proposal["groups"]
                if g["heuristic_level"] == "component"
            )
            require(
                members == EXPECTED["dependency_components"],
                "GROUP_LITERAL_LEIDEN_MEMBERSHIP",
            )
            require(
                len(json.loads((output / "raw_engine.json").read_bytes())) == 3,
                "GROUP_REAL_ENGINE_RECEIPT",
            )
        require(
            proposal["metrics"]["weighted_edges"] == EXPECTED["weighted_edges"],
            "GROUP_WEIGHTED_FACTS",
        )
        require(
            proposal["coverage"]["omitted_by_reason"] == EXPECTED["omitted"],
            "GROUP_FACT_ACCOUNTING",
        )
        for omitted in proposal["omitted_graph_facts"]:
            require(
                omitted["fact"]
                == proposal["relationships"][omitted["relationship_index"]],
                "GROUP_FACT_ACCOUNTING",
            )
        require(
            json.loads((output / "raw_graph.json").read_bytes()) == request["graph"],
            "GROUP_NATIVE_COMPLETE_GRAPH",
        )


def test_settings_reach_real_engine(monkeypatch, tmp_path):
    from chunker.clustering.engine import ClusteringEngine

    request = make_request(mode="dependency_assisted")
    request["settings"].update(
        seed=731,
        coarse_resolution=0.75,
        fine_resolution=1.75,
        infrastructure_threshold=0.8,
    )
    request["settings"]["weights"]["call_weight"] = 0.4
    product = runpy.run_path(str(DRIVER))
    value = product["normalize"](request)
    calls = []
    original = ClusteringEngine._run_leiden

    def witness(self, resolution):
        result = original(self, resolution)
        calls.append(
            {
                "seed": self.seed,
                "resolution": resolution,
                "weight": self.weight_config.call_weight,
                "threshold": self.infrastructure_threshold,
                "result": copy.deepcopy(result),
            }
        )
        return result

    monkeypatch.setattr(ClusteringEngine, "_run_leiden", witness)
    result, raw = product["compute"](value)
    (tmp_path / "settings-witness.json").write_text(
        json.dumps({"calls": calls, "raw_engine": raw, "groups": result["groups"]})
    )
    require(
        calls
        and all(
            r["seed"] == 731 and r["weight"] == 0.4 and r["threshold"] == 0.8
            for r in calls
        ),
        "GROUP_SETTINGS_PASSTHROUGH",
    )
    require(
        {r["resolution"] for r in calls} == {0.75, 1.75}, "GROUP_SETTINGS_PASSTHROUGH"
    )
    require(
        result["groups"] and raw and all(r["result"] for r in calls),
        "GROUP_REAL_ENGINE_WITNESS",
    )


def test_twelve_fresh_permutations(tmp_path):
    request = make_request(mode="dependency_assisted")
    reference = None
    hash_probes = {}
    for root in ("first", "archive/relocated"):
        for seed in ("1", "17", "101"):
            for reverse in (False, True):
                current = (
                    RECIPE["reverse_arrays"](request)
                    if reverse
                    else copy.deepcopy(request)
                )
                cp, output = launch(
                    tmp_path / root / (seed + str(reverse)), current, seed=seed
                )
                proposal = accepted(cp, output)
                verify_proposal(current, proposal)
                encoded = (output / "proposal.json").read_bytes()
                if reference is not None:
                    require(encoded == reference, "GROUP_CANONICAL_ORDER")
                reference = encoded
                require(
                    json.loads((output / "raw_graph.json").read_bytes())
                    == current["graph"],
                    "GROUP_RAW_MULTISETS",
                )
                probe = json.loads((output / "operational.json").read_bytes())[
                    "resources"
                ]["native_hash_probe"]
                if seed in hash_probes:
                    require(hash_probes[seed] == probe, "GROUP_EFFECTIVE_HASH_SEED")
                hash_probes[seed] = probe
    require(len(set(hash_probes.values())) == 3, "GROUP_EFFECTIVE_HASH_SEED")


def test_profile_change_and_ordered_native_data(tmp_path):
    original = make_request()
    requests = [original, copy.deepcopy(original), copy.deepcopy(original)]
    requests[1]["settings"]["seed"] = 52
    requests[2]["graph"]["metadata"]["unknown_ordered"].reverse()
    requests[2]["source_binding"]["graph_digest"] = RECIPE["hashed"](
        "graph", RECIPE["normalized_graph"](requests[2]["graph"])
    )
    proposals = []
    for i, request in enumerate(requests):
        cp, output = launch(tmp_path / str(i), request)
        proposals.append(accepted(cp, output))
        verify_proposal(request, proposals[-1])
    require(
        proposals[0]["profile_digest"] != proposals[1]["profile_digest"],
        "GROUP_PROFILE_BINDING",
    )
    require(
        proposals[0]["groups"] == proposals[1]["groups"],
        "GROUP_SETTINGS_NEED_NOT_CHANGE_PARTITION",
    )
    require(
        proposals[0]["proposal_digest"] != proposals[2]["proposal_digest"],
        "GROUP_OPAQUE_ARRAY_IDENTITY",
    )
    cp, output = launch(
        tmp_path / "stale", requests[1], expected=RECIPE["pins"](original)
    )
    rejected(cp, output, "group_identity")


@pytest.mark.parametrize(
    ("case", "reason", "exit_code"),
    [
        ("shape", "group_schema", 1),
        ("bool", "group_schema", 1),
        ("relation_file", "group_schema", 1),
        ("relation_internal", "group_schema", 1),
        ("identity", "group_identity", 1),
        ("source_byte", "group_identity", 1),
        ("membership", "group_membership", 1),
        ("coverage", "group_coverage", 1),
        ("budget", "group_budget", 1),
        ("dependency", "group_dependency", 2),
        ("missing_dependency", "group_dependency", 2),
        ("artifact", "group_dependency", 2),
    ],
)
def test_refusal_precedence(tmp_path, case, reason, exit_code):
    request = make_request()
    expected = None
    if case == "shape":
        request["extra"] = True
    elif case == "bool":
        request["settings"]["seed"] = True
    elif case == "relation_file":
        request["graph"]["relationships"][0]["file"] = ["not-a-path"]
    elif case == "relation_internal":
        request["graph"]["relationships"][0]["is_internal"] = "not-a-boolean"
    elif case == "identity":
        expected = {**RECIPE["pins"](request), "request": "0" * 64}
    elif case == "source_byte":
        request["producer"]["source_files"][0]["sha256"] = "0" * 64
    elif case == "membership":
        request["policy"]["unassigned_ids"].append("a1")
        request["source_binding"]["coverage_records"][0]["status"] = "failed"
        request["settings"]["limits"]["max_symbols"] += 1
    elif case == "coverage":
        request["source_binding"]["coverage_records"][0][
            "status"
        ] = "processed_no_symbols"
        request["source_binding"]["coverage_digest"] = RECIPE["hashed"](
            "coverage", request["source_binding"]["coverage_records"]
        )
        request["settings"]["limits"]["max_symbols"] += 1
    elif case == "budget":
        request["settings"]["limits"]["max_symbols"] += 1
        request["producer"]["dependencies"][0]["version"] = "missing"
    elif case == "dependency":
        next(
            r for r in request["producer"]["dependencies"] if r["name"] == "leidenalg"
        )["version"] = "missing"
    elif case == "missing_dependency":
        request["producer"]["dependencies"] = [
            r for r in request["producer"]["dependencies"] if r["name"] != "leidenalg"
        ]
    elif case == "artifact":
        next(
            r for r in request["producer"]["dependencies"] if r["name"] == "leidenalg"
        )["artifact_sha256"] = ("0" * 64)
    if case in ("membership", "coverage"):
        request["source_binding"]["coverage_digest"] = RECIPE["hashed"](
            "coverage", request["source_binding"]["coverage_records"]
        )
    cp, output = launch(tmp_path / case, request, expected=expected)
    rejected(cp, output, reason, exit_code)


@pytest.mark.parametrize(
    "raw", [b'{"schema":1,"schema":2}', b'{"x":NaN}', b'{"x":"\\ud800"}']
)
def test_json_refusals(tmp_path, raw):
    request = make_request()
    cp, output = launch(tmp_path, request, raw=raw)
    rejected(cp, output, "group_schema")


def test_transport_and_output_refusal(tmp_path):
    request = make_request()
    cp, output = launch(tmp_path / "big", request, raw=b" " * (16777216 + 1))
    rejected(cp, output, "group_budget")
    case = tmp_path / "existing"
    case.mkdir()
    (case / "output").mkdir()
    marker = case / "output/keep"
    marker.write_bytes(b"unchanged")
    cp, output = launch(case, request)
    require(
        cp.returncode == 1
        and json.loads(cp.stderr)["reason"] == "group_schema"
        and marker.read_bytes() == b"unchanged",
        "GROUP_OUTPUT_NOT_OVERWRITTEN",
    )


@pytest.mark.parametrize("count", [0, 1, 2])
def test_empty_single_and_no_edge(tmp_path, count):
    graph = {
        "symbol_lookup": {
            str(i): {"name": str(i), "file": "empty.py"} for i in range(count)
        },
        "relationships": [],
    }
    for mode in ("declared_boundaries", "dependency_assisted"):
        request = make_request(mode=mode, graph=graph)
        cp, output = launch(tmp_path / mode, request)
        proposal = accepted(cp, output)
        verify_proposal(request, proposal)
        require(
            {m for g in proposal["groups"] for m in g["members"]}
            == set(graph["symbol_lookup"]),
            "GROUP_EMPTY_PARTITION",
        )


@pytest.mark.parametrize("mode", ["declared_boundaries", "dependency_assisted"])
def test_empty_declared_boundary_and_explicit_empty_neutral_bucket(tmp_path, mode):
    # treesitter-chunker#514 N8: a declared boundary with no members is retained
    # policy evidence but yields no group, whereas the neutral unassigned bucket
    # is always reported, even when it is empty.
    request = make_request(mode=mode)
    leftover = request["policy"]["unassigned_ids"]
    require(leftover == ["u"], "GROUP_EMPTY_FIXTURE")
    request["policy"]["membership"] += [
        {"boundary_id": "E", "members": []},
        {"boundary_id": "U", "members": leftover},
    ]
    request["policy"]["unassigned_ids"] = []
    cp, output = launch(tmp_path, request)
    proposal = accepted(cp, output)
    verify_proposal(request, proposal)
    require(
        {"boundary_id": "E", "members": []} in proposal["policy"]["membership"],
        "GROUP_EMPTY_BOUNDARY_RETAINED",
    )
    cited = {r["boundary_id"] for g in proposal["groups"] for r in g["reasons"]}
    require(cited == {"A", "B", "U", None}, "GROUP_EMPTY_BOUNDARY_NO_GROUP")
    neutral = [
        g
        for g in proposal["groups"]
        if [r["boundary_id"] for r in g["reasons"]] == [None]
    ]
    level = "unassigned" if mode == "declared_boundaries" else "container"
    require(
        [(g["members"], g["heuristic_level"], g["parent_id"]) for g in neutral]
        == [([], level, None)],
        "GROUP_EMPTY_NEUTRAL_EXPLICIT",
    )


def native_request(tmp):
    from chunker.symbol_graph import (
        assemble_symbol_graph,
        extract_symbol_facts_for_file,
    )

    root = tmp / "source"
    root.mkdir(parents=True)
    (root / "one.py").write_bytes(
        b"def alpha():\n    return 1\n\ndef beta():\n    return alpha() + alpha()\n"
    )
    (root / "empty.py").write_bytes(b"# deliberately empty producer result\n")
    (root / "vendor").mkdir()
    (root / "vendor/secret.py").write_bytes(b"DO_NOT_COLLECT = 1\n")
    scope_driver = ROOT / "tools/governed_scope.py"
    declaration = {
        "version": "governed_scope.v1",
        "repo_id": "genuine-fixture",
        "source_revision": "fixture-native-v1",
        "ownership_assertion": {
            "decision_ref": "test-only",
            "remaining_regular_files": "governed",
        },
        "rules": [],
        "generated_inclusions": [],
        "limits": {"max_files": 100, "max_bytes": 100000},
    }
    request = {
        "declaration": declaration,
        "source_root": str(root),
        "root_metadata": {
            "source_revision": "fixture-native-v1",
            "submodule_paths": [],
        },
        "expected_driver_sha256": hashlib.sha256(scope_driver.read_bytes()).hexdigest(),
    }
    path = tmp / "scope.json"
    path.write_text(json.dumps(request))
    selected = tmp / "selected"
    cp = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(scope_driver),
            "prepare",
            "--request",
            str(path),
            "--output",
            str(selected),
        ],
        capture_output=True,
        timeout=20,
    )
    require(cp.returncode == 0, "GROUP_REAL_SCOPE:" + cp.stderr.decode())
    selection = json.loads((selected / "selection.json").read_bytes())
    receipt = json.loads((selected / "selection-receipt.json").read_bytes())
    facts, coverage = [], []
    for record in selection["included_files"]:
        fact = extract_symbol_facts_for_file(
            selected / "stage" / record["path"],
            selected / "stage",
            language="python",
            fail_fast=True,
        )
        facts.append(fact)
        coverage.append(
            {
                "path": record["path"],
                "status": (
                    "processed" if fact["symbol_lookup"] else "processed_no_symbols"
                ),
                "diagnostic_refs": [],
            }
        )
    graph = assemble_symbol_graph(
        facts, total_files=len(facts), resolution_mode="permissive"
    )
    scope = {
        name: receipt[name]
        for name in (
            "selection_digest",
            "declaration_digest",
            "metadata_digest",
            "included_inventory_digest",
        )
    }
    scope.update(
        repo_id="genuine-fixture",
        source_revision="fixture-native-v1",
        driver_sha256=request["expected_driver_sha256"],
        native_identity_profile={
            "producer": "extract_symbol_facts_for_file/assemble_symbol_graph",
            "version": "6.0.0-source-overlay",
            "symbol_id_algorithm": "native-definition-or-node-id-occurrence",
            "graph_encoding": "native-complete-json",
            "relocation_comparability": True,
        },
    )
    return make_request(
        mode="dependency_assisted", graph=graph, coverage=coverage, scope=scope
    )


def test_genuine_native_relocation_and_reversal(tmp_path):
    first = native_request(tmp_path / "first")
    second = native_request(tmp_path / "archive/second")
    require(
        RECIPE["normalized_graph"](first["graph"])
        == RECIPE["normalized_graph"](second["graph"]),
        "GROUP_NATIVE_RELOCATION_PROFILE",
    )
    require(
        first["graph"]["symbol_lookup"] and len(first["graph"]["call_facts"]) == 2,
        "GROUP_GENUINE_CALL_FACTS",
    )
    reference = None
    for i, request in enumerate(
        [
            first,
            RECIPE["reverse_arrays"](first),
            second,
            RECIPE["reverse_arrays"](second),
        ]
    ):
        cp, output = launch(tmp_path / ("group-" + str(i)), request)
        proposal = accepted(cp, output)
        verify_proposal(request, proposal)
        actual = (output / "proposal.json").read_bytes()
        require(
            reference is None or reference == actual, "GROUP_GENUINE_CANONICAL_ORDER"
        )
        reference = actual


def test_root_dependent_identity_remains_noncomparable(tmp_path):
    first = make_request()
    second = copy.deepcopy(first)
    second["graph"]["symbol_lookup"]["a1"]["native_root_identity"] = "/different/root"
    for request in (first, second):
        request["source_binding"]["native_identity_profile"][
            "relocation_comparability"
        ] = False
        request["source_binding"]["graph_digest"] = RECIPE["hashed"](
            "graph", RECIPE["normalized_graph"](request["graph"])
        )
    outputs = []
    for i, request in enumerate((first, second)):
        cp, output = launch(tmp_path / str(i), request)
        outputs.append(accepted(cp, output))
    require(
        outputs[0]["proposal_digest"] != outputs[1]["proposal_digest"],
        "GROUP_NONCOMPARABLE_NATIVE_PROFILE",
    )


def test_invalid_engine_partition_refuses(monkeypatch):
    from chunker.clustering.engine import ClusteringEngine

    original = ClusteringEngine.cluster

    def invalid(self, symbols, relationships):
        result = original(self, symbols, relationships)
        result["hierarchy"]["members"].append("invented")
        return result

    monkeypatch.setattr(ClusteringEngine, "cluster", invalid)
    product = runpy.run_path(str(DRIVER))
    try:
        product["compute"](
            product["normalize"](make_request(mode="dependency_assisted"))
        )
    except product["GroupError"] as error:
        require(error.reason == "group_compute", "GROUP_INVALID_PARTITION")
    else:
        raise AssertionError("GROUP_INVALID_PARTITION")


def test_frozen_fake_vector_is_serialization_only():
    vector = EXPECTED["normalization_vector"]
    product = runpy.run_path(str(DRIVER))
    for key in ("canonical", "reversed"):
        normalized = product["normalize"](vector[key])
        require(
            product["encoded"](normalized).decode()
            == vector["expected"]["canonical_request_utf8"],
            "GROUP_NORMALIZATION_VECTOR",
        )
        pins = product["identities"](normalized)
        require(
            pins["request"] == vector["expected"]["request_digest"]
            and pins["profile"] == vector["expected"]["profile_digest"],
            "GROUP_NORMALIZATION_VECTOR",
        )


def test_recipe_wire_paths_are_posix():
    from pathlib import PurePosixPath, PureWindowsPath

    product = runpy.run_path(str(DRIVER))
    for flavor, root in (
        (PureWindowsPath, "C:/checkout"),
        (PurePosixPath, "/checkout"),
    ):
        path = flavor(root) / "chunker" / "clustering" / "engine.py"
        wire = RECIPE["wire_path"](path, flavor(root))
        require(
            wire == "chunker/clustering/engine.py" and product["relative"](wire),
            "GROUP_WIRE_PATH",
        )
    require(
        not product["relative"]("chunker\\clustering\\engine.py"),
        "GROUP_WIRE_PATH_REFUSES_NATIVE",
    )


def test_recipe_producer_uses_wire_path(monkeypatch):
    from pathlib import PureWindowsPath
    import types

    produce = RECIPE["producer"]
    scope = produce.__globals__
    base = PureWindowsPath("C:/checkout")
    content = {
        base / "tools" / "governed_group.py": b"adapter control bytes",
        base / "chunker" / "fixture.py": b"chunker control bytes",
        base / "uv.lock": b"lock control bytes",
    }

    class Leaf:
        # Windows-flavored stand-in for only the operations the producer uses.
        def __init__(self, pure):
            self.pure = pure

        def __truediv__(self, name):
            return Leaf(self.pure / name)

        def __lt__(self, other):
            return self.pure < other.pure

        def rglob(self, pattern):
            require(
                self.pure == base / "chunker" and pattern == "*.py",
                "GROUP_PRODUCER_SHIM",
            )
            return iter([Leaf(base / "chunker" / "fixture.py")])

        def read_bytes(self):
            return content[self.pure]

        def relative_to(self, other):
            return self.pure.relative_to(other.pure)

    def windows_root(value):
        require(value == "C:/checkout", "GROUP_PRODUCER_SHIM")
        return Leaf(base)

    helper = scope["wire_path"]
    calls = []

    def spy(path, root):
        calls.append((path.pure, root.pure))
        return helper(path, root)

    monkeypatch.setitem(scope, "Path", windows_root)
    monkeypatch.setitem(scope, "wire_path", spy)
    monkeypatch.setitem(
        scope, "metadata", types.SimpleNamespace(distributions=lambda: iter(()))
    )
    produced = produce("C:/checkout", ANCHOR)
    product = runpy.run_path(str(DRIVER))
    require(
        produced["source_files"]
        == [
            {
                "path": "tools/governed_group.py",
                "sha256": hashlib.sha256(b"adapter control bytes").hexdigest(),
            },
            {
                "path": "chunker/fixture.py",
                "sha256": hashlib.sha256(b"chunker control bytes").hexdigest(),
            },
        ]
        and all(product["relative"](row["path"]) for row in produced["source_files"])
        and calls
        == [
            (base / "tools" / "governed_group.py", base),
            (base / "chunker" / "fixture.py", base),
        ]
        and produced["lock_sha256"] == hashlib.sha256(b"lock control bytes").hexdigest()
        and produced["dependencies"] == [],
        "GROUP_PRODUCER_WIRE_PATH",
    )


def test_site_disabled_dependencies_are_setup_nonpass(tmp_path):
    request = make_request()
    path = tmp_path / "request.json"
    path.write_bytes(RECIPE["canonical"](request))
    pins = RECIPE["pins"](request)
    output = tmp_path / "output"
    command = [
        sys.executable,
        "-I",
        "-S",
        str(DRIVER),
        "--request",
        str(path),
        "--output",
        str(output),
    ]
    for key in ("request", "source-binding", "profile"):
        command.extend(["--expected-" + key + "-sha256", pins[key]])
    cp = subprocess.run(command, capture_output=True, timeout=20)
    rejected(cp, output, "group_dependency", 2)


def test_negative_zero_and_partial_coverage(tmp_path):
    first = make_request()
    first["settings"]["weights"]["same_file_bonus"] = 0.0
    second = copy.deepcopy(first)
    second["settings"]["weights"]["same_file_bonus"] = -0.0
    partial = copy.deepcopy(first)
    partial["source_binding"]["coverage_records"].append(
        {
            "path": "skipped.py",
            "status": "skipped_by_producer_filter",
            "diagnostic_refs": ["literal-filter"],
        }
    )
    partial["source_binding"]["coverage_digest"] = RECIPE["hashed"](
        "coverage", partial["source_binding"]["coverage_records"]
    )
    outputs = []
    for i, request in enumerate((first, second, partial)):
        cp, output = launch(tmp_path / str(i), request)
        outputs.append(accepted(cp, output))
    require(
        outputs[0]["profile_digest"] != outputs[1]["profile_digest"],
        "GROUP_NATIVE_NEGATIVE_ZERO",
    )
    require(outputs[0]["groups"] == outputs[1]["groups"], "GROUP_NATIVE_NO_ROUNDING")
    require(
        outputs[2]["coverage"]["status"] == "partial"
        and len(outputs[2]["coverage"]["unknowns"]) == 1,
        "GROUP_PARTIAL_NOT_ABSENCE",
    )


def test_nonnamespace_module_without_file_refuses(monkeypatch):
    import types

    monkeypatch.setitem(
        sys.modules,
        "chunker.unbound_control",
        types.ModuleType("chunker.unbound_control"),
    )
    product = runpy.run_path(str(DRIVER))
    try:
        product["load_engine"](make_request())
    except product["GroupError"] as error:
        require(error.reason == "group_dependency", "GROUP_NAMESPACE_BINDING")
    else:
        raise AssertionError("GROUP_NAMESPACE_BINDING")


def test_nonempty_normalization_arrays(tmp_path):
    request = make_request()
    request["graph"]["errors"] = ["z-note", "a-note"]
    request["policy"]["override_refs"] = [{"ref": "z"}, {"ref": "a"}]
    request["graph"]["symbol_lookup"]["v"] = {"name": "v", "file": "empty.py"}
    request["policy"]["unassigned_ids"].append("v")
    for record in request["source_binding"]["coverage_records"]:
        record["diagnostic_refs"] = ["z-note", "a-note"]
    request["source_binding"]["graph_digest"] = RECIPE["hashed"](
        "graph", RECIPE["normalized_graph"](request["graph"])
    )
    request["source_binding"]["coverage_digest"] = RECIPE["hashed"](
        "coverage", RECIPE["normalized"](request)["source_binding"]["coverage_records"]
    )
    reversed_request = RECIPE["reverse_arrays"](request)
    require(
        RECIPE["pins"](request) == RECIPE["pins"](reversed_request),
        "GROUP_ALL_N_ARRAY_PINS",
    )
    results = []
    for i, current in enumerate((request, reversed_request)):
        cp, output = launch(tmp_path / str(i), current)
        proposal = accepted(cp, output)
        verify_proposal(current, proposal)
        results.append((output / "proposal.json").read_bytes())
    require(results[0] == results[1], "GROUP_ALL_N_ARRAYS")


def test_output_cap_is_aggregate_of_published_artifacts(tmp_path):
    request = make_request()
    padding = "x" * 9_000_000
    request["graph"]["metadata"]["budget_padding"] = padding
    request["source_binding"]["graph_digest"] = RECIPE["hashed"](
        "graph", RECIPE["normalized_graph"](request["graph"])
    )
    raw = RECIPE["canonical"](request)
    # The padding is retained verbatim in request.json and raw_graph.json: each file
    # is under the cap, while their sum alone exceeds it.
    require(len(raw) <= 16777216 < 2 * len(padding), "GROUP_AGGREGATE_PRECONDITION")
    cp, output = launch(tmp_path, request, raw=raw)
    rejected(cp, output, "group_compute")
    require(
        sorted(p.name for p in output.iterdir()) == ["diagnostic.json"]
        and json.loads((output / "diagnostic.json").read_bytes())
        == {"reason": "group_compute"},
        "GROUP_AGGREGATE_OUTPUT_BUDGET",
    )


def setup_refusal(code, out, err, output, kind):
    lines = err.splitlines()
    try:
        first = json.loads(lines[0]) if lines else None
    except ValueError:
        first = None
    require(
        code == 2
        and first == {"reason": "group_setup", "type": kind}
        and b"Traceback (most recent call last):" not in lines
        and not out,
        "GROUP_SETUP_EXIT:" + json.dumps({"exit": code, "stderr_lines": len(lines)}),
    )
    require(not output.exists(), "GROUP_SETUP_NO_OUTPUT")


def run_main(monkeypatch, capsysbinary, tmp_path, request):
    path = tmp_path / "request.json"
    path.write_bytes(RECIPE["canonical"](request))
    pins = RECIPE["pins"](request)
    output = tmp_path / "output"
    argv = [str(DRIVER), "--request", str(path), "--output", str(output)]
    for key in ("request", "source-binding", "profile"):
        argv += ["--expected-" + key + "-sha256", pins[key]]
    monkeypatch.setattr(sys, "argv", argv)
    product = runpy.run_path(str(DRIVER))
    code = product["main"]()
    return code, capsysbinary.readouterr(), output


def test_unexpected_parent_setup_error_exits_two(monkeypatch, capsysbinary, tmp_path):
    import importlib.metadata

    # The recipe enumerates installed distributions, so build it before patching.
    request = make_request()
    real = importlib.metadata.distributions

    class Nameless:
        metadata = {"Name": None}
        version = "0"

    monkeypatch.setattr(
        importlib.metadata, "distributions", lambda: [*real(), Nameless()]
    )
    code, captured, output = run_main(monkeypatch, capsysbinary, tmp_path, request)
    setup_refusal(code, captured.out, captured.err, output, "TypeError")


def test_supervision_access_denied_is_setup_and_child_dead_at_exit(tmp_path):
    import psutil

    marker = tmp_path / "child.pid"
    prelude = (
        "import pathlib, psutil\n"
        "def denied(pid):\n"
        "    pathlib.Path(" + repr(str(marker)) + ").write_text(str(pid))\n"
        "    raise psutil.AccessDenied(pid)\n"
        "psutil.Process = denied\n"
    )
    cp, output = launch(tmp_path, make_request(), prelude=prelude)
    setup_refusal(cp.returncode, cp.stdout, cp.stderr, output, "AccessDenied")
    require(marker.exists(), "GROUP_SETUP_CHILD_REAPED")
    # Dead after interpreter exit. Multiprocessing's exit-time join would also reap
    # this non-daemon child, so this does not isolate run_worker's own cleanup.
    require(not psutil.pid_exists(int(marker.read_text())), "GROUP_SETUP_CHILD_REAPED")


@pytest.mark.parametrize(
    "interrupt",
    [KeyboardInterrupt, SystemExit],
    ids=["KeyboardInterrupt", "SystemExit"],
)
def test_cancellation_is_not_setup(monkeypatch, capsysbinary, interrupt):
    product = runpy.run_path(str(DRIVER))
    signal = interrupt("control")

    def cancelled(args):
        raise signal

    monkeypatch.setitem(product["main"].__globals__, "execute", cancelled)
    argv = [str(DRIVER), "--request", "unused", "--output", "unused"]
    for key in ("request", "source-binding", "profile"):
        argv += ["--expected-" + key + "-sha256", "unused"]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        code = product["main"]()
    except interrupt as caught:
        require(caught is signal, "GROUP_CANCELLATION_PROPAGATES")
    else:
        raise AssertionError(
            "GROUP_CANCELLATION_PROPAGATES:" + json.dumps({"returned": code})
        )
    require(capsysbinary.readouterr().err == b"", "GROUP_CANCELLATION_PROPAGATES")
