"""Grammar self-test utilities use current APIs without network installation."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from chunker.grammar_management.core import GrammarManager, load_compiled_grammar
from chunker.grammar_management.testing import (
    CLIValidator,
    IntegrationTester,
    PerformanceBenchmark,
    SystemValidator,
    run_complete_test_suite,
)
from chunker.parser import get_parser
from tree_sitter_language_pack import cache_dir


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"


@pytest.mark.parametrize(
    "component", [CLIValidator, SystemValidator, PerformanceBenchmark]
)
def test_default_auxiliary_roots_are_disposable_and_outside_home(
    tmp_path, monkeypatch, component
):
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    home = tmp_path / "operator-home"
    home.mkdir()
    sentinel = home / "service.py"
    sentinel.write_bytes(source)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    with component() as tester:
        owned_root = tester.test_dir
        assert owned_root.is_dir()
        assert not owned_root.is_relative_to(home)
        assert list(home.iterdir()) == [sentinel]
    assert not owned_root.exists()
    assert sentinel.read_bytes() == source


@pytest.mark.parametrize(
    "component", [CLIValidator, SystemValidator, PerformanceBenchmark]
)
def test_auxiliary_cleanup_preserves_supplied_root(tmp_path, component):
    root = tmp_path / "caller-root"
    root.mkdir()
    sentinel = root / "service.py"
    sentinel.write_bytes(FIXTURE.read_bytes())
    with component(test_dir=root) as tester:
        assert tester.test_dir == root
    assert sentinel.read_bytes() == FIXTURE.read_bytes()
    assert not get_parser("python").parse(sentinel.read_bytes()).root_node.has_error


def test_error_scenarios_observe_local_rejections_and_retire_simulations(tmp_path):
    tester = IntegrationTester(tmp_path / "scenarios")
    results = tester.test_error_scenarios()
    assert results["recovery_successful"] == ["invalid_language", "corrupt_grammar"]
    assert results["recovery_failed"] == []
    assert results["status"] == "unsupported"
    assert set(results["unsupported"]) == {
        "network_failure",
        "disk_full",
        "permission_denied",
    }
    assert all(results["unsupported"].values())


def test_cli_reports_actual_local_checks_and_unsupported_operations(tmp_path):
    with CLIValidator(test_dir=tmp_path / "cli") as tester:
        commands = tester.test_all_commands()
        assert commands["status"] == "unsupported", commands
        assert commands["passed"] == ["list", "info", "remove", "test", "validate"]
        assert commands["failed"] == []
        assert set(commands["unsupported"]) == {"versions", "fetch", "build"}
        help_result = tester.test_help_and_documentation()
        assert help_result["status"] == "pass", help_result
        assert help_result["help_available"] is True
        assert "usability_score" not in tester.test_user_experience()


def test_performance_retirement_does_not_touch_ambient_cache(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    sentinel = home / "cache-sentinel"
    sentinel.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with PerformanceBenchmark() as tester:
        operations = tester.benchmark_grammar_operations()
        assert operations["status"] == "pass", operations
        assert set(operations["operations"]) == {"discover", "get_info"}
        assert operations["errors"] == []
        assert tester.test_scalability()["status"] == "unsupported"
        assert tester.optimize_performance()["status"] == "unsupported"
    assert list(home.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == FIXTURE.read_bytes()


def test_system_validation_uses_supplied_valid_configuration(tmp_path):
    tester = IntegrationTester(tmp_path / "config")
    tester.config.set("cache.max_size_mb", 1)
    with SystemValidator(tester.grammar_manager, tester.config) as health:
        result = health.validate_configuration()
        assert result["status"] == "valid", result
        assert result["config_items"]["cache"]["max_size_mb"] == 1


def test_complete_suite_returns_truthful_results_and_opt_in_report(
    tmp_path, monkeypatch
):
    home = tmp_path / "home"
    home.mkdir()
    sentinel = home / "service.py"
    sentinel.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    root = tmp_path / "caller-root"
    root.mkdir()
    (root / "sentinel").write_text("preserve", encoding="utf-8")
    report = tmp_path / "explicit-report.json"
    result = run_complete_test_suite(test_dir=root, report_path=report)
    assert result["status"] == "unsupported", result
    assert result["summary"]["failed"] == 0
    assert result["summary"]["unsupported"] > 0
    assert result["test_suites"]["integration"]["workflow"]["status"] == "unsupported"
    assert json.loads(report.read_text(encoding="utf-8")) == result
    assert (root / "sentinel").read_text(encoding="utf-8") == "preserve"
    assert list(home.iterdir()) == [sentinel]


@pytest.mark.parametrize(
    "fault", ["missing_result", "malformed_result", "crash", "timeout"]
)
def test_real_worker_failure_is_reaped_before_private_root_cleanup(
    tmp_path, monkeypatch, fault
):
    from chunker.grammar_management.testing import _run_test_worker

    root = tmp_path / "caller-root"
    root.mkdir()
    sentinel = root / "sentinel"
    sentinel.write_bytes(FIXTURE.read_bytes())
    pid_file = tmp_path / "worker.pid"
    real_run = subprocess.run
    programs = {
        "missing_result": "pass",
        "malformed_result": "Path(sys.argv[1]).write_text('{', encoding='utf-8')",
        "crash": "os._exit(7)",
        "timeout": "time.sleep(30)",
    }

    def faulty_worker(command, **kwargs):
        program = (
            "import os, sys, time; from pathlib import Path; "
            "Path(sys.argv[2]).write_text(str(os.getpid())); " + programs[fault]
        )
        return real_run(
            [sys.executable, "-I", "-c", program, command[-1], str(pid_file)],
            **kwargs,
        )

    monkeypatch.setattr(
        "chunker.grammar_management.testing.subprocess.run", faulty_worker
    )
    result = _run_test_worker(root, "workflow", None, "python", None, timeout=0.5)
    assert result["status"] == "fail", result
    assert result["errors"]
    assert not psutil.pid_exists(int(pid_file.read_text()))
    assert list(root.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == FIXTURE.read_bytes()


def test_complete_suite_native_fixture_and_owned_cleanup(tmp_path, monkeypatch):
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
    grammar = ROOT / "build" / f"python{suffix}"
    if not grammar.exists():
        grammar = Path(cache_dir()) / f"libtree_sitter_python{suffix}"
    assert grammar.is_file()
    owned_roots = []
    real_mkdtemp = __import__("tempfile").mkdtemp

    def observe_root(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        if kwargs.get("prefix") == "grammar_test_":
            owned_roots.append(Path(path))
        return path

    monkeypatch.setattr(
        "chunker.grammar_management.testing.tempfile.mkdtemp", observe_root
    )
    result = run_complete_test_suite(sample_path=FIXTURE, grammar_path=grammar)
    workflow = result["test_suites"]["integration"]["workflow"]
    assert workflow["status"] == "pass", result
    assert workflow["workflows_tested"] == ["discovery", "validation"]
    assert result["summary"]["failed"] == 0
    supplied_root = tmp_path / "fixture-root"
    supplied_root.mkdir()
    disposable_library = supplied_root / f"python{suffix}"
    disposable_library.write_bytes(grammar.read_bytes())
    disposable_result = run_complete_test_suite(
        test_dir=supplied_root, sample_path=FIXTURE, grammar_path=disposable_library
    )
    assert (
        disposable_result["test_suites"]["integration"]["workflow"]["status"] == "pass"
    )
    disposable_library.unlink()
    assert supplied_root.exists()
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(\n", encoding="utf-8")
    rejected = run_complete_test_suite(sample_path=invalid, grammar_path=grammar)
    assert rejected["status"] == "fail", rejected
    assert rejected["summary"]["failed"] > 0
    assert owned_roots and all(not path.exists() for path in owned_roots)


def test_explicit_report_failure_is_visible(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_complete_test_suite(report_path=tmp_path / "missing-parent" / "report.json")


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
    health.cleanup()
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
