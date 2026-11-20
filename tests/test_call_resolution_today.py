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


def test_manifest_sha256_is_pinned() -> None:
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


@pytest.mark.parametrize("tree", TREES)
def test_today_matches_off_mode_output(tree: str) -> None:
    """Each call's ``today`` edge equals the live off-mode symbol graph."""
    table = _table(tree)
    for run in (run for run in RUNS if run.tree == tree):
        graph = extract_symbol_graph(run.path, run.language)
        assert graph["errors"] == []
        assert _today_calls(graph) == table["runs"][run.label]["calls"], run.run_id


@pytest.mark.parametrize("run_id", [run.run_id for run in RUNS])
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

    bumped = json.loads(json.dumps(recorded))
    for entry in bumped["files"].values():
        entry["key_payload"]["tool_version"] = "0.0.0-test"
        entry["cache_key"] = "boundary:changed"
    assert capture.compare_cache_keys(recorded, bumped) == []

    changed = json.loads(json.dumps(recorded))
    first = next(iter(changed["files"]))
    changed["files"][first]["key_payload"]["resolution_mode"] = "strict"
    assert capture.compare_cache_keys(recorded, changed) == [
        f"{first}: payload field resolution_mode differs"
    ]
