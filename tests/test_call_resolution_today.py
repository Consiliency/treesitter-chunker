"""Off-mode output equals today (treesitter-chunker#682, PR 0).

Two pins, both derived by running unmodified main (plan sections 10.1 and 11.2):

- ``expected/<tree>.json`` records each call's ``today`` edge. The test
  checks it against the live off-mode symbol graph.
- ``off_mode_baseline/`` holds canonical off-mode documents for every run.
  ``scripts/capture_call_resolution_off_baseline.py`` regenerates them in
  memory, cold and then warm-incremental, and the test compares them with the
  committed bytes. The sha256 of ``MANIFEST.sha256`` is pinned here.

CI runs this module on unmodified product code, which proves the baseline came
from it. Never regenerate the baseline to make a product change pass. A lock
change regenerates it in its own pull request with no product change.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from chunker.symbol_graph import extract_symbol_graph

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture_call_resolution_off_baseline.py"

# sha256 of tests/fixtures/call_resolution/off_mode_baseline/MANIFEST.sha256.
MANIFEST_SHA256 = "654e61b3421457cea62291373bb90dc65d3e5575bbfdc4ecdc7b4a77737124a8"


def _load_capture() -> ModuleType:
    name = "capture_call_resolution_off_baseline"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture = _load_capture()
RUNS = capture.discover_runs()
TREES = sorted({run.tree for run in RUNS})
EXPECTED = capture.FIXTURES / "expected"

# The keys PR 0 pins. Later PRs add per-mode fields and ``pr`` to the same
# records by hand; the ``today`` check compares only this projection, so those
# additions never touch the PR 0 pin.
PR0_CALL_KEYS = (
    "file",
    "line",
    "call_span",
    "callee_span",
    "caller",
    "reference",
    "call_site_id",
    "today",
)
PR0_TODAY_KEYS = ("resolution", "candidates", "candidate_ids")
# Trees whose runs emit no call edges at all on main: Java, Kotlin and C# emit
# none (plan section 10.5), and the Greenfield Kotlin trees have none either.
ZERO_CALL_TREES = {
    "clo-kotlin",
    "ctl-csharp",
    "ctl-java",
    "ctl-kotlin",
    "rt-java",
    "rt-kotlin",
}
# treesitter-chunker#687: collect_source_files sorts Path objects, and WindowsPath
# sorts case-insensitively, so py-namespace-dir (D.py, D/sub.py, app.py, other.py)
# emits its symbol-graph lists in another order on Windows. Parity views,
# digests, cache keys and ``today`` still match. Never regenerate for this
# (plan section 11.2).
WINDOWS_PATH_ORDER = pytest.mark.xfail(
    sys.platform == "win32",
    strict=True,
    reason=(
        "treesitter-chunker#687: case-insensitive WindowsPath sort in "
        "collect_source_files"
    ),
)
WINDOWS_PATH_ORDER_RUNS = {"py-namespace-dir/default"}
# Product code whose change must never land together with a baseline change.
PRODUCT_PREFIXES = ("chunker/", "cli/")
BASELINE_MANIFEST = "tests/fixtures/call_resolution/off_mode_baseline/MANIFEST.sha256"


def _today_calls(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Every call edge, in emitted order, in the expected-table shape."""
    symbols = graph["symbol_lookup"]

    def label(symbol_id: str) -> str:
        symbol = symbols[symbol_id]
        return f"{symbol['file']}:{symbol['line']}:{symbol['qualified_name']}"

    calls = []
    for edge in graph["relationships"]:
        if edge["type"] != "calls":
            continue
        calls.append(
            {
                "file": edge["file"],
                "line": edge["line"],
                "call_span": [
                    edge["location"]["byte_start"],
                    edge["location"]["byte_end"],
                ],
                "callee_span": [edge["callee_byte_start"], edge["callee_byte_end"]],
                "caller": symbols[edge["from"]]["qualified_name"],
                "reference": edge["reference"],
                "call_site_id": edge["call_site_id"],
                "today": {
                    "resolution": edge["resolution"],
                    "candidates": [
                        label(candidate) for candidate in edge["candidates"]
                    ],
                    "candidate_ids": list(edge["candidates"]),
                },
            }
        )
    return calls


def _table(tree: str) -> dict[str, Any]:
    return json.loads((EXPECTED / f"{tree}.json").read_text(encoding="utf-8"))


def _pr0_projection(call: dict[str, Any]) -> dict[str, Any]:
    """The PR 0 keys of one expected-table record."""
    projected = {key: call[key] for key in PR0_CALL_KEYS}
    projected["today"] = {key: call["today"][key] for key in PR0_TODAY_KEYS}
    return projected


def test_manifest_sha256_is_pinned() -> None:
    assert capture.MANIFEST.relative_to(ROOT).as_posix() == BASELINE_MANIFEST
    assert hashlib.sha256(capture.MANIFEST.read_bytes()).hexdigest() == MANIFEST_SHA256


def test_committed_documents_match_the_manifest() -> None:
    assert capture.check_manifest() == []


def test_manifest_lists_every_run() -> None:
    listed = capture.read_manifest()
    run_ids = {name.rsplit("/", 1)[0] for name in listed if "/" in name}
    assert run_ids == {run.run_id for run in RUNS}
    digests = json.loads(capture.DIGESTS.read_text(encoding="utf-8"))
    assert sorted(digests) == sorted(run.run_id for run in RUNS)


def test_expected_tables_cover_every_tree_and_run() -> None:
    assert sorted(path.stem for path in EXPECTED.glob("*.json")) == TREES
    for tree in TREES:
        table = _table(tree)
        runs = {run.label: run for run in RUNS if run.tree == tree}
        assert table["tree"] == tree
        assert sorted(table["runs"]) == sorted(runs)
        for label, run in runs.items():
            assert table["runs"][label]["root"] == run.root
            assert table["runs"][label]["language"] == run.language


def test_zero_call_trees_are_exactly_the_empty_tables() -> None:
    empty = {
        tree
        for tree in TREES
        if not any(run["calls"] for run in _table(tree)["runs"].values())
    }
    assert empty == ZERO_CALL_TREES


@pytest.mark.parametrize("tree", TREES)
def test_today_matches_off_mode_output(tree: str) -> None:
    """Each call's ``today`` edge equals the live off-mode symbol graph."""
    table = _table(tree)
    for run in (run for run in RUNS if run.tree == tree):
        graph = extract_symbol_graph(run.path, run.language)
        assert graph["errors"] == []
        expected = [_pr0_projection(call) for call in table["runs"][run.label]["calls"]]
        assert _today_calls(graph) == expected, run.run_id


@pytest.mark.parametrize(
    "run_id",
    [
        pytest.param(
            run.run_id,
            marks=WINDOWS_PATH_ORDER if run.run_id in WINDOWS_PATH_ORDER_RUNS else (),
        )
        for run in RUNS
    ],
)
def test_off_mode_matches_the_baseline(run_id: str) -> None:
    """Cold and warm-incremental off-mode documents equal the committed baseline."""
    (run,) = (run for run in RUNS if run.run_id == run_id)
    assert capture.check_run(run) == []


def _copy_run(tmp_path: Path, run: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the capture module at a private copy of one tree and its baseline."""
    fixtures = tmp_path / "call_resolution"
    shutil.copytree(capture.FIXTURES / run.root, fixtures / run.root)
    baseline = fixtures / "off_mode_baseline"
    shutil.copytree(capture.BASELINE / run.run_id, baseline / run.run_id)
    shutil.copy2(capture.DIGESTS, baseline / capture.DIGESTS.name)
    monkeypatch.setattr(capture, "FIXTURES", fixtures)
    monkeypatch.setattr(capture, "BASELINE", baseline)
    monkeypatch.setattr(capture, "DIGESTS", baseline / capture.DIGESTS.name)
    monkeypatch.setattr(capture, "MANIFEST", baseline / "MANIFEST.sha256")


def test_check_detects_a_changed_baseline_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation M13: one changed byte of committed off-mode output fails."""
    (run,) = (run for run in RUNS if run.run_id == "r9-ts/default")
    _copy_run(tmp_path, run, monkeypatch)
    target = capture.BASELINE / run.run_id / "symbol_graph.permissive.json"
    data = bytearray(target.read_bytes())
    data[-2] = ord(" ") if data[-2] != ord(" ") else ord("\t")
    target.write_bytes(bytes(data))
    assert capture.check_run(run) == [
        f"differs: {run.run_id}/symbol_graph.permissive.json"
    ]


def test_check_detects_changed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A change in extraction output (here, a changed source) fails the check."""
    (run,) = (run for run in RUNS if run.run_id == "ts-kind-filter/default")
    _copy_run(tmp_path, run, monkeypatch)
    source = capture.FIXTURES / run.root / "x.ts"
    source.write_bytes(
        source.read_bytes() + b"\nexport function extra() { return t(); }\n"
    )
    problems = capture.check_run(run)
    assert f"differs: {run.run_id}/symbol_graph.permissive.json" in problems
    assert f"differs: {run.run_id}/boundary_ir.strict.parity.json" in problems
    assert f"parity digests differ: {run.run_id}" in problems


def test_cache_key_comparison_tolerates_only_version_fields() -> None:
    """Version bumps alone do not fail the cache-key pin; other fields do."""
    (run,) = (run for run in RUNS if run.run_id == "r9-ts/default")
    path = capture.BASELINE / run.run_id / "cache_keys.permissive.json"
    recorded = json.loads(path.read_text(encoding="utf-8"))
    assert recorded["files"], "expected recorded cache keys"
    assert capture.compare_cache_keys(recorded, recorded) == []
    for payload in (entry["key_payload"] for entry in recorded["files"].values()):
        assert "call_resolution" not in payload
        assert "scope_facts" not in payload

    from chunker.boundary.cache import build_boundary_cache_key

    def rekeyed(document: dict[str, Any]) -> dict[str, Any]:
        for entry in document["files"].values():
            entry["cache_key"] = build_boundary_cache_key(entry["key_payload"])
        return document

    bumped = json.loads(json.dumps(recorded))
    for entry in bumped["files"].values():
        entry["key_payload"]["tool_version"] = "0.0.0-test"
    assert capture.compare_cache_keys(recorded, rekeyed(bumped)) == []

    first = next(iter(recorded["files"]))
    changed = json.loads(json.dumps(recorded))
    changed["files"][first]["key_payload"]["resolution_mode"] = "strict"
    assert capture.compare_cache_keys(recorded, rekeyed(changed)) == [
        f"{first}: payload field resolution_mode differs",
        f"{first}: cache key differs at unchanged versions",
    ]

    added = json.loads(json.dumps(recorded))
    added["files"][first]["key_payload"]["call_resolution"] = "name"
    assert capture.compare_cache_keys(recorded, rekeyed(added)) == [
        f"{first}: payload fields differ (added ['call_resolution'], removed [])"
    ]

    underived = json.loads(json.dumps(recorded))
    underived["files"][first]["cache_key"] = "boundary:not-derived"
    assert capture.compare_cache_keys(recorded, underived) == [
        f"{first}: current key does not derive from its payload",
        f"{first}: cache key differs at unchanged versions",
    ]


def test_today_projection_ignores_later_fields() -> None:
    """PRs 1-6 may add fields to expected records without editing the pin."""
    call = _table("r9-ts")["runs"]["default"]["calls"][0]
    extended = json.loads(json.dumps(call))
    extended["pr"] = 2
    extended["structural"] = {"outcome": "local", "edge": "resolved"}
    extended["today"]["note"] = "added later"
    assert _pr0_projection(extended) == _pr0_projection(call)
    assert set(_pr0_projection(call)) == set(call)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
        timeout=60,
    )


def test_baseline_manifest_never_changes_with_product_code() -> None:
    """A baseline change and a product change never share one diff (plan 11.2).

    Compares HEAD with its merge base against ``origin/main``. CI checks out
    with full history, so the ref exists there; elsewhere the test skips.
    """
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a Git checkout")
    base = _git("merge-base", "origin/main", "HEAD")
    if base.returncode != 0 or not base.stdout.strip():
        pytest.skip("origin/main is not available for a merge base")
    diff = _git("diff", "--name-only", "--no-renames", base.stdout.strip(), "HEAD")
    assert diff.returncode == 0, diff.stderr
    product = _product_paths_changed_with_baseline(set(diff.stdout.splitlines()))
    assert product == [], (
        f"{BASELINE_MANIFEST} changed together with product code {product}; "
        "regenerate the baseline only in its own pull request with no product change"
    )


def _product_paths_changed_with_baseline(changed: set[str]) -> list[str]:
    if BASELINE_MANIFEST not in changed:
        return []
    return sorted(path for path in changed if path.startswith(PRODUCT_PREFIXES))


def test_baseline_policy_flags_only_mixed_diffs() -> None:
    assert _product_paths_changed_with_baseline({BASELINE_MANIFEST}) == []
    assert _product_paths_changed_with_baseline({"chunker/symbol_graph.py"}) == []
    assert _product_paths_changed_with_baseline(
        {BASELINE_MANIFEST, "chunker/symbol_graph.py", "cli/main.py", "tests/x.py"}
    ) == ["chunker/symbol_graph.py", "cli/main.py"]
