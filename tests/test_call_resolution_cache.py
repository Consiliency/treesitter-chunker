"""Boundary cache keys and records for opt-in call resolution (#682).

Plan section 4.4 and harness check 13:

- keys for each mode differ, with and without semantic resolvers, because
  both key branches hash ``call_resolution`` and ``call_resolution_version``;
- off-mode payloads, keys and records are unchanged: they match the values
  PR 0 recorded and never contain ``scope_facts``;
- an on-mode record whose ``scope_facts`` is missing or malformed is a safe
  miss;
- switching modes on one cache directory is a cold run in both directions.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from chunker.boundary import adapter, dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.cache import (
    BoundaryCacheRecord,
    build_boundary_cache_key,
    load_cache_index,
)
from chunker.call_resolution.facts import CALL_RESOLUTION_FACT_VERSIONS
from tests import call_resolution_harness as harness

FIXTURES = harness.FIXTURES
MODE = "structural"


class _Resolver:
    resolver_id = "tests.call_resolution"
    resolver_version = "0.1.0"
    supported_languages = ("python", "typescript")

    def enrich(self, context: Any) -> tuple[()]:
        return ()


def _payload(language: str | None = "typescript", **kwargs: Any) -> dict[str, Any]:
    return adapter._cache_key_payload(
        display_path="x.ts",
        content_hash="sha1:" + "0" * 40,
        language=language,
        resolution_mode="strict",
        fail_fast=False,
        **kwargs,
    )


@pytest.mark.parametrize("semantic", [False, True])
def test_keys_differ_per_mode_in_both_branches(semantic: bool) -> None:
    extra: dict[str, Any] = {"semantic_resolvers": (_Resolver(),)} if semantic else {}
    keys = {
        mode: adapter._build_boundary_cache_key(_payload(call_resolution=mode, **extra))
        for mode in ("name", MODE)
    }
    assert len(set(keys.values())) == 2
    on_payload = _payload(call_resolution=MODE, **extra)
    bumped = {**on_payload, "call_resolution_version": "999"}
    assert adapter._build_boundary_cache_key(bumped) != keys[MODE]


def test_off_mode_payload_and_key_are_unchanged() -> None:
    for extra in ({}, {"semantic_resolvers": (_Resolver(),)}):
        omitted = _payload(**extra)
        named = _payload(call_resolution="name", **extra)
        assert named == omitted
        assert "call_resolution" not in named
        assert "call_resolution_version" not in named
        assert adapter._build_boundary_cache_key(
            named
        ) == adapter._build_boundary_cache_key(omitted)
    plain = _payload()
    assert adapter._build_boundary_cache_key(plain) == build_boundary_cache_key(plain)


def test_on_mode_payload_names_the_mode_and_family_version() -> None:
    assert _payload("typescript", call_resolution=MODE)["call_resolution"] == MODE
    versions = {
        language: _payload(language, call_resolution=MODE)["call_resolution_version"]
        for language in ("typescript", "tsx", "javascript", "python", "go")
    }
    assert versions == {
        "typescript": CALL_RESOLUTION_FACT_VERSIONS["js"],
        "tsx": CALL_RESOLUTION_FACT_VERSIONS["js"],
        "javascript": CALL_RESOLUTION_FACT_VERSIONS["js"],
        "python": CALL_RESOLUTION_FACT_VERSIONS["python"],
        "go": None,
    }


@pytest.mark.parametrize("resolution_mode", harness.RESOLUTION_MODES)
def test_off_mode_payloads_match_the_pr0_record(resolution_mode: str) -> None:
    capture = harness.load_capture()
    (run,) = (run for run in capture.discover_runs() if run.run_id == "r9-ts/default")
    recorded = json.loads(
        (
            capture.BASELINE / run.run_id / f"cache_keys.{resolution_mode}.json"
        ).read_text(encoding="utf-8")
    )
    current_files = {}
    for display_path, entry in recorded["files"].items():
        old = entry["key_payload"]
        payload = adapter._cache_key_payload(
            display_path=display_path,
            content_hash=old["content_hash"],
            language=old["language"],
            resolution_mode=resolution_mode,
            fail_fast=False,
            call_resolution="name",
        )
        current_files[display_path] = {
            "cache_key": adapter._build_boundary_cache_key(payload),
            "key_payload": payload,
        }
    current = {"volatile_fields": recorded["volatile_fields"], "files": current_files}
    assert capture.compare_cache_keys(recorded, current) == []


def _records(cache_dir: Path) -> list[dict[str, Any]]:
    index = load_cache_index(cache_dir)
    return [
        json.loads(
            (cache_dir / (key.replace(":", "_") + ".json")).read_text(encoding="utf-8")
        )
        for key in index.records.values()
    ]


def _tree(tmp_path: Path, tree: str = "authored/mixed-family") -> Path:
    root = tmp_path / "tree"
    shutil.copytree(FIXTURES / tree, root)
    return root


def test_off_mode_records_never_contain_scope_facts(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    cache_dir = tmp_path / "cache"
    extract_boundary_ir(root, incremental=True, cache_dir=cache_dir)
    records = _records(cache_dir)
    assert records
    for record in records:
        assert "scope_facts" not in record["symbol_facts"]
        assert "call_resolution" not in record["key_payload"]


def test_on_mode_records_store_scope_facts(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    cache_dir = tmp_path / "cache"
    extract_boundary_ir(
        root, incremental=True, cache_dir=cache_dir, call_resolution=MODE
    )
    records = _records(cache_dir)
    assert records
    for record in records:
        assert record["key_payload"]["call_resolution"] == MODE
        assert "scope_facts" in record["symbol_facts"]
        BoundaryCacheRecord.from_json(record)


def _spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path: Path, *args: Any, **kwargs: Any) -> Any:
        calls.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    return calls


@pytest.mark.parametrize(
    "corruption",
    ["missing", "not-an-object", "bad-version", "bad-outcome", "supported-go"],
)
def test_malformed_on_mode_scope_facts_are_a_safe_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    root = _tree(tmp_path)
    cache_dir = tmp_path / "cache"
    cold = extract_boundary_ir(root, call_resolution=MODE)
    extract_boundary_ir(
        root, incremental=True, cache_dir=cache_dir, call_resolution=MODE
    )
    index = load_cache_index(cache_dir)
    target_path = "c.go" if corruption == "supported-go" else "x.ts"
    record_path = cache_dir / (index.records[target_path].replace(":", "_") + ".json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    scope_facts = record["symbol_facts"].get("scope_facts")
    if corruption == "missing":
        del record["symbol_facts"]["scope_facts"]
    elif corruption == "not-an-object":
        record["symbol_facts"]["scope_facts"] = []
    elif corruption == "bad-version":
        scope_facts["version"] = "0"
    elif corruption == "bad-outcome":
        key = next(iter(scope_facts["bindings"]))
        scope_facts["bindings"][key] = {"outcome": "resolved"}
    else:
        scope_facts["supported"] = True
    with pytest.raises(ValueError, match="scope facts"):
        BoundaryCacheRecord.from_json(record)
    record_path.write_text(json.dumps(record), encoding="utf-8")
    calls = _spy(monkeypatch)
    warm = extract_boundary_ir(
        root, incremental=True, cache_dir=cache_dir, call_resolution=MODE
    )
    # The record is re-extracted; impact analysis may also refresh dependents.
    assert target_path in calls
    assert dumps_boundary_ir(warm) == dumps_boundary_ir(cold)


def test_switching_modes_is_cold_in_both_directions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    cache_dir = tmp_path / "cache"
    files = sorted(path.name for path in root.iterdir())
    cold = {
        mode: extract_boundary_ir(root, call_resolution=mode) for mode in ("name", MODE)
    }
    calls = _spy(monkeypatch)
    for mode in ("name", MODE, "name", MODE):
        calls.clear()
        result = extract_boundary_ir(
            root, incremental=True, cache_dir=cache_dir, call_resolution=mode
        )
        assert sorted(calls) == files, mode
        assert dumps_boundary_ir(result) == dumps_boundary_ir(cold[mode])
    calls.clear()
    warm = extract_boundary_ir(
        root, incremental=True, cache_dir=cache_dir, call_resolution=MODE
    )
    assert calls == []
    assert dumps_boundary_ir(warm) == dumps_boundary_ir(cold[MODE])


def test_semantic_on_mode_cold_and_warm_agree(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    cache_dir = tmp_path / "cache"
    options: dict[str, Any] = {
        "semantic_resolvers": (_Resolver(),),
        "call_resolution": MODE,
    }
    cold = extract_boundary_ir(root, **options)
    first = extract_boundary_ir(root, incremental=True, cache_dir=cache_dir, **options)
    second = extract_boundary_ir(root, incremental=True, cache_dir=cache_dir, **options)
    assert dumps_boundary_ir(first) == dumps_boundary_ir(cold)
    assert dumps_boundary_ir(second) == dumps_boundary_ir(cold)
    assert cold["run"]["options"]["call_resolution"] == MODE
    assert cold["schema_version"] == "3.1"
    for record in _records(cache_dir):
        assert record["key_payload"]["call_resolution"] == MODE
        assert record["key_payload"]["semantic_schema_version"] == "3.1"
