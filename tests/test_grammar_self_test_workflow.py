"""Grammar self-test utilities use current APIs without network installation."""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from chunker.grammar_management.core import GrammarManager, load_compiled_grammar
from chunker.grammar_management.testing import IntegrationTester, SystemValidator
from chunker.parser import get_parser
from tree_sitter_language_pack import cache_dir


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"


def test_isolated_workflow_parses_fixture_and_rejects_missing_grammar(
    tmp_path: Path, monkeypatch
) -> None:
    source = FIXTURE.read_bytes()
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    grammar_path = ROOT / "build" / f"python{suffix}"
    if not grammar_path.exists():
        grammar_path = Path(cache_dir()) / f"libtree_sitter_python{suffix}"
    assert grammar_path.exists()
    assert (
        not load_compiled_grammar(grammar_path, "python")
        .parse(source)
        .root_node.has_error
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    work_dir = tmp_path / "self-test"
    tester = IntegrationTester(work_dir)
    assert tester.dir_manager.base_dir == work_dir
    assert tester.cache_manager.cache_dir == work_dir / "cache"

    valid = tester.test_complete_workflow(FIXTURE, "python", grammar_path)
    assert valid["status"] == "pass", valid
    assert valid["workflows_tested"] == ["discovery", "validation"]
    assert valid["errors"] == []

    invalid_path = tmp_path / "invalid.py"
    invalid_path.write_text("def broken(\n", encoding="utf-8")
    invalid = tester.test_complete_workflow(invalid_path, "python", grammar_path)
    assert invalid["status"] == "fail", invalid
    assert invalid["errors"] == ["Sample 1: Syntax error in parse tree"]

    missing = tester.test_complete_workflow(FIXTURE, "missing_grammar", grammar_path)
    assert missing["status"] == "fail", missing
    assert missing["errors"]
    assert tester.test_results["complete_workflow"] == missing

    health = SystemValidator(tester.grammar_manager, tester.config)
    assert health.check_system_health()["status"] == "healthy"
    integration = tester.test_cross_component_integration()
    assert integration["status"] == "pass", integration
    assert "config-cache" in integration["integration_points"]
    tester.cleanup()
    assert work_dir.exists()
    assert list(home.iterdir()) == []


@pytest.mark.skipif(sys.platform != "linux", reason="Registry discovers .so files")
def test_health_report_distinguishes_parseable_and_broken_local_grammars(
    tmp_path: Path,
) -> None:
    source_grammar = ROOT / "build/python.so"
    if not source_grammar.exists():
        source_grammar = Path(cache_dir()) / "libtree_sitter_python.so"
    assert source_grammar.exists()

    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    python_grammar = user_dir / "libpython.so"
    shutil.copyfile(source_grammar, python_grammar)
    (user_dir / "libjavascript.so").touch()

    source = FIXTURE.read_bytes()
    assert (
        not load_compiled_grammar(python_grammar, "python")
        .parse(source)
        .root_node.has_error
    )

    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "cache",
    )
    report = manager.check_grammar_health()

    assert set(report) == {"python", "javascript"}
    assert report["python"]["is_healthy"] is True
    assert report["python"]["errors"] == []
    assert report["javascript"]["is_healthy"] is False
    assert "empty" in " ".join(report["javascript"]["errors"]).lower()
    assert all(entry["last_checked"] > 0 for entry in report.values())


def test_manager_cache_cleanup_preserves_recent_parseable_source_and_entries(
    tmp_path: Path,
) -> None:
    source = FIXTURE.read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    cache_dir = tmp_path / "cache"
    downloads_dir = cache_dir / "downloads"
    builds_dir = cache_dir / "builds"
    downloads_dir.mkdir(parents=True)
    builds_dir.mkdir()
    stale_source = downloads_dir / "stale.py"
    fresh_source = builds_dir / "fresh.py"
    stale_source.write_bytes(source)
    fresh_source.write_bytes(source)
    now = time.time()
    stale_time = now - 25 * 86400
    fresh_time = now - 15 * 86400
    os.utime(stale_source, (stale_time, stale_time))
    os.utime(fresh_source, (fresh_time, fresh_time))
    (cache_dir / "validation_cache.json").write_text(
        json.dumps(
            {
                "stale": {"timestamp": stale_time},
                "fresh": {"timestamp": fresh_time},
            }
        ),
        encoding="utf-8",
    )

    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=cache_dir,
    )
    result = manager.cleanup_cache(older_than_days=20)

    assert result == {
        "files_removed": 2,
        "bytes_freed": len(source),
        "directories_cleaned": ["downloads", "validation_cache"],
        "errors": [],
    }
    assert not stale_source.exists()
    assert fresh_source.read_bytes() == source
    assert not parser.parse(fresh_source.read_bytes()).root_node.has_error
    assert json.loads(
        (cache_dir / "validation_cache.json").read_text(encoding="utf-8")
    ) == {"fresh": {"timestamp": fresh_time}}
