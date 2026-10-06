"""Observable compatibility results and local grammar selection."""

from dataclasses import asdict
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    BreakingChangeType,
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    CompatibilityResult,
    GrammarTester,
    SelectionCriterion,
    SmartSelector,
    TestResult as GrammarTestResult,
)
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarValidator,
    ValidationLevel,
    load_compiled_grammar,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "helper_type", [CompatibilityChecker, GrammarTester], ids=["checker", "tester"]
)
@pytest.mark.parametrize(
    "supplied_validator", [False, True], ids=["default", "supplied"]
)
def test_compatibility_helpers_confine_cache_roots(
    tmp_path, monkeypatch, helper_type, supplied_validator
):
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    tree = get_parser("python").parse(source)
    assert tree.root_node.child_count > 0
    assert not tree.root_node.has_error
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    cache = tmp_path / "grammar-cache"
    manager = GrammarManager(
        user_dir=tmp_path / "user", package_dir=tmp_path / "package", cache_dir=cache
    )
    supplied = (
        GrammarValidator(tmp_path / "supplied-cache") if supplied_validator else None
    )
    helper = helper_type(manager, validator=supplied)
    assert not (home / ".cache" / "treesitter-chunker").exists()
    if supplied is not None:
        assert helper.validator is supplied
    expected = tmp_path / "supplied-cache" if supplied is not None else cache
    if supplied is not None:
        assert expected != cache
    validators = [
        manager._validator,
        manager._installer._validator,
        manager._registry._installer._validator,
    ]
    assert all(validator._cache_dir == cache for validator in validators)
    assert helper.validator._cache_dir == expected
    success, errors = helper.validator.test_parse_samples(
        "python", [source.decode("utf-8")]
    )
    assert success and errors == []
    assert not helper.validator._validation_cache.exists()
    for index, validator in enumerate([helper.validator, *validators]):
        candidate = tmp_path / f"directory-not-grammar-{index}"
        candidate.mkdir()
        result = validator.validate_grammar(candidate, "python", ValidationLevel.BASIC)
        assert not result.is_valid
        assert result.errors == [f"Grammar path is not a file: {candidate}"]
        records = json.loads(validator._validation_cache.read_text(encoding="utf-8"))
        assert records
        assert all(
            not record["is_valid"] and record["errors"] == result.errors
            for record in records.values()
        )
    assert not (home / ".cache" / "treesitter-chunker").exists()
    assert (cache / "validation_cache.json").is_file()
    assert (expected / "validation_cache.json").is_file()


@pytest.mark.parametrize(
    ("language", "fixture"),
    [
        ("python", "tests/fixtures/boundary_ir/repos/python/app/service.py"),
        ("javascript", "tests/fixtures/boundary_ir/repos/javascript/service.js"),
    ],
)
def test_supported_fixture_parsers_accept_real_source(
    language: str, fixture: str
) -> None:
    source = (ROOT / fixture).read_bytes()
    tree = get_parser(language).parse(source)
    assert not tree.root_node.has_error


def test_error_pattern_analysis_counts_real_python_parse_failures(
    tmp_path: Path, monkeypatch
) -> None:
    valid = (ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py").read_text(
        encoding="utf-8"
    )
    samples = [valid, valid + "\ndef broken(\n", valid + "\nclass Broken(:\n"]
    parser = get_parser("python")
    assert not parser.parse(samples[0].encode()).root_node.has_error
    assert all(
        parser.parse(sample.encode()).root_node.has_error for sample in samples[1:]
    )

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))
    analysis = tester.analyze_error_patterns("python", samples)

    assert analysis["language"] == "python"
    assert analysis["total_samples"] == 3
    assert analysis["successful_parses"] == 1
    assert analysis["failed_parses"] == 2
    assert analysis["failure_rate"] == pytest.approx(2 / 3)
    assert analysis["error_patterns"] == {"syntax_error": 2}
    assert analysis["common_errors"] == [("syntax_error", 2)]
    assert not home.exists()


def test_comprehensive_syntax_result_follows_real_parse_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_text(encoding="utf-8")
    malformed = source + "\ndef broken(\n"
    parser = get_parser("python")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse(malformed.encode()).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))

    tester.test_suites["python"] = [source]
    accepted = tester.run_comprehensive_test("python", ["syntax"])
    assert accepted.success is True
    assert accepted.sample_results[0]["success"] is True
    assert accepted.sample_results[0]["samples_tested"] == 1
    assert accepted.sample_results[0]["errors"] == []

    tester.test_suites["python"] = [source, malformed]
    rejected = tester.run_comprehensive_test("python", ["syntax"])
    assert rejected.success is False
    assert rejected.sample_results[0]["success"] is False
    assert rejected.sample_results[0]["samples_tested"] == 2
    assert rejected.sample_results[0]["errors"] == [
        "Sample 2: Syntax error in parse tree"
    ]
    assert not home.exists()


def test_comprehensive_test_rejects_unknown_type_before_running_checks(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error
    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))
    tester.test_suites["python"] = [source.decode("utf-8")]

    result = tester.run_comprehensive_test("python", ["syntax", "not-a-test"])
    assert result.success is False
    assert result.error_message == "Unknown test type(s): not-a-test"
    assert result.sample_results == []
    assert not home.exists()


def test_parse_benchmark_counts_only_successful_fixture_samples(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_text(encoding="utf-8")
    malformed = source + "\ndef broken(\n"
    parser = get_parser("python")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse(malformed.encode()).root_node.has_error

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    manager = GrammarManager(
        user_dir=tmp_path / "user",
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))
    tester.test_suites["python"] = [source, malformed]
    assert not parser.parse(
        tester._generate_test_code("python", 3).encode()
    ).root_node.has_error
    assert parser.parse(
        tester._generate_test_code("python", 6).encode()
    ).root_node.has_error

    benchmark = tester.benchmark_parsing_performance("python", [3, 6])
    assert benchmark["language"] == "python"
    assert benchmark["sample_sizes"] == [3, 6]
    accepted, rejected = benchmark["results"]
    assert accepted["sample_size"] == 3
    assert accepted["success"] is True
    assert accepted["errors"] == []
    assert rejected["sample_size"] == 6
    assert rejected["success"] is False
    assert rejected["errors"] == ["Sample 1: Syntax error in parse tree"]
    assert benchmark["summary"]["successful_tests"] == 1
    assert benchmark["summary"]["total_tests"] == 2
    assert benchmark["summary"]["avg_parse_time"] == pytest.approx(
        accepted["parse_time"]
    )
    assert not home.exists()


def test_comprehensive_performance_result_follows_real_parse_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_text(encoding="utf-8")
    malformed = source + "\ndef broken(\n"
    parser = get_parser("python")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse(malformed.encode()).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))

    tester.test_suites["python"] = [source]
    accepted = tester.run_comprehensive_test("python", ["performance"])
    assert accepted.success is True
    assert all(entry["success"] for entry in accepted.sample_results[0]["results"])
    assert accepted.performance_metrics["avg_throughput_lines_per_sec"] > 0

    tester.test_suites["python"] = [malformed]
    rejected = tester.run_comprehensive_test("python", ["performance"])
    assert rejected.success is False
    assert all(not entry["success"] for entry in rejected.sample_results[0]["results"])
    assert "avg_throughput_lines_per_sec" not in rejected.performance_metrics
    assert not home.exists()


def test_comprehensive_memory_result_follows_real_parse_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    psutil = pytest.importorskip("psutil")
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_text(encoding="utf-8")
    malformed = source + "\ndef broken(\n"
    parser = get_parser("python")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse(malformed.encode()).root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=tmp_path / "package",
        cache_dir=tmp_path / "cache",
    )
    tester = GrammarTester(manager, GrammarValidator(tmp_path / "validation"))

    tester.test_suites["python"] = [source]
    accepted = tester.run_comprehensive_test("python", ["memory"])
    assert accepted.success is True
    assert accepted.sample_results[0]["success"] is True

    tester.test_suites["python"] = [malformed]
    rejected = tester.run_comprehensive_test("python", ["memory"])
    assert rejected.success is False
    assert rejected.sample_results[0]["success"] is False

    memory_probes = 0

    class FailingProcess:
        def memory_info(self):
            nonlocal memory_probes
            memory_probes += 1
            if memory_probes == 2:
                raise ImportError("memory probe failed")
            return SimpleNamespace(rss=1024 * 1024)

    monkeypatch.setattr(psutil, "Process", lambda _pid: FailingProcess())
    tester.test_suites["python"] = [source]
    probe_error = tester.run_comprehensive_test("python", ["memory"])
    assert memory_probes == 2
    assert probe_error.success is False
    assert probe_error.sample_results == [
        {"test_type": "memory", "error": "memory probe failed"}
    ]
    assert not home.exists()


def test_compatibility_reason_score_selection_and_history(
    tmp_path: Path, monkeypatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("The checked-in grammar builds as a Linux shared library")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    source = (
        ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
    ).read_text(encoding="utf-8")
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    (user_dir / "libbaml.so").touch()
    package_library = package_dir / "libbaml.so"
    grammar_src = ROOT / "packages/baml-grammar/src"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(grammar_src),
            str(grammar_src / "parser.c"),
            "-o",
            str(package_library),
        ],
        check=True,
        capture_output=True,
    )
    assert (
        not load_compiled_grammar(package_library, "baml")
        .parse(source.encode("utf-8"))
        .root_node.has_error
    )

    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "cache",
    )
    database = CompatibilityDatabase(tmp_path / "history.db")
    checker = CompatibilityChecker(manager, database)
    incompatible = checker.check_compatibility("baml", code_samples=[source])
    assert incompatible.level == CompatibilityLevel.INCOMPATIBLE
    assert incompatible.score == 0.0
    assert any("empty" in issue.lower() for issue in incompatible.issues)
    recorded = database.get_compatibility_result("baml", "unknown")
    assert recorded is not None
    history = asdict(recorded)

    compatible = checker.check_compatibility(
        "baml", code_samples=[source], grammar_path=package_library
    )
    assert compatible.level in {
        CompatibilityLevel.COMPATIBLE,
        CompatibilityLevel.DEGRADED,
    }
    assert compatible.score > incompatible.score
    assert compatible.test_results is not None
    assert compatible.test_results["successful_samples"] == 1

    selected = SmartSelector(manager, checker, database).select_best_grammar(
        "baml", criteria_weights={SelectionCriterion.COMPATIBILITY: 1.0}
    )
    assert selected is not None
    assert selected.grammar_path == package_library
    assert selected.compatibility_score > 0.0
    preserved = database.get_compatibility_result("baml", "unknown")
    assert preserved is not None
    assert asdict(preserved) == history


def test_breaking_changes_compare_persisted_real_parse_outcomes(
    tmp_path: Path, monkeypatch
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    parser = get_parser("python")
    valid_tree = parser.parse(source)
    invalid_tree = parser.parse(source + b"\ndef broken(\n")
    assert not valid_tree.root_node.has_error
    assert invalid_tree.root_node.has_error

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "cache",
    )
    database_path = tmp_path / "history.db"
    database = CompatibilityDatabase(database_path)
    old_result = CompatibilityResult(
        language="python",
        grammar_version="1.0",
        language_version=None,
        level=CompatibilityLevel.COMPATIBLE,
        performance_impact={"average_parse_time": 0.02},
        test_results={"success_rate": float(not valid_tree.root_node.has_error)},
    )
    new_result = CompatibilityResult(
        language="python",
        grammar_version="2.0",
        language_version=None,
        level=CompatibilityLevel.INCOMPATIBLE,
        issues=["Fixture contains parse errors"],
        performance_impact={"average_parse_time": 0.04},
        test_results={"success_rate": float(not invalid_tree.root_node.has_error)},
    )
    database.store_compatibility_result(old_result)
    database.store_compatibility_result(new_result)
    checker = CompatibilityChecker(
        manager,
        CompatibilityDatabase(database_path),
        validator=GrammarValidator(tmp_path / "validator"),
    )

    changes = checker.detect_breaking_changes("python", "1.0", "2.0")
    assert [change["type"] for change in changes] == [
        BreakingChangeType.ABI_INCOMPATIBLE.value,
        BreakingChangeType.PERFORMANCE_DEGRADED.value,
        BreakingChangeType.STRUCTURE_CHANGED.value,
    ]
    assert changes[0]["issues"] == new_result.issues
    assert changes[1]["old_time"] == 0.02
    assert changes[1]["new_time"] == 0.04
    assert "100.0%" in changes[1]["description"]
    assert changes[2]["impact"] == "high"

    for version in ("3.0", "4.0"):
        database.store_compatibility_result(
            CompatibilityResult(
                language="python",
                grammar_version=version,
                language_version=None,
                level=CompatibilityLevel.COMPATIBLE,
                performance_impact={"average_parse_time": 0.02},
                test_results={"success_rate": 1.0},
            )
        )
    assert checker.detect_breaking_changes("python", "3.0", "4.0") == []
    assert not home.exists()


@pytest.mark.parametrize(
    "old_timing",
    [
        {"average_parse_time": 0.0},
        {"other_metric": 1.0},
        {"average_parse_time": None},
        {"average_parse_time": -0.02},
    ],
    ids=["zero", "missing", "unavailable", "negative"],
)
def test_unavailable_timing_preserves_persisted_real_parse_regressions(
    tmp_path: Path, old_timing
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    parser = get_parser("python")
    valid_tree = parser.parse(source)
    invalid_tree = parser.parse(source + b"\ndef broken(\n")
    assert not valid_tree.root_node.has_error
    assert invalid_tree.root_node.has_error

    native_spec = importlib.util.find_spec("tree_sitter_language_pack._native")
    assert native_spec is not None and native_spec.origin is not None
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    shutil.copyfile(native_spec.origin, user_dir / "libpython.so")
    manager = GrammarManager(
        user_dir=user_dir, package_dir=package_dir, cache_dir=tmp_path / "cache"
    )
    database_path = tmp_path / "history.db"
    database = CompatibilityDatabase(database_path)
    old_result = CompatibilityResult(
        language="python",
        grammar_version="1.0",
        language_version=None,
        level=CompatibilityLevel.COMPATIBLE,
        performance_impact=old_timing,
        test_results={"success_rate": float(not valid_tree.root_node.has_error)},
    )
    new_result = CompatibilityResult(
        language="python",
        grammar_version="2.0",
        language_version=None,
        level=CompatibilityLevel.INCOMPATIBLE,
        issues=["Fixture contains parse errors"],
        performance_impact={"average_parse_time": 0.04},
        test_results={"success_rate": float(not invalid_tree.root_node.has_error)},
    )
    database.store_compatibility_result(old_result)
    database.store_compatibility_result(new_result)
    reopened = CompatibilityDatabase(database_path)
    stored = reopened.get_compatibility_result("python", "1.0")
    assert stored is not None and stored.performance_impact == old_timing
    checker = CompatibilityChecker(manager, reopened)
    changes = checker.detect_breaking_changes("python", "1.0", "2.0")
    assert [change["type"] for change in changes] == [
        BreakingChangeType.ABI_INCOMPATIBLE.value,
        BreakingChangeType.STRUCTURE_CHANGED.value,
    ]
    assert changes[0]["issues"] == new_result.issues
    assert changes[1]["impact"] == "high"


def test_performance_trends_filter_language_age_and_preserve_order(
    tmp_path: Path,
) -> None:
    parsed = {}
    for language, fixture in (
        ("python", "tests/fixtures/boundary_ir/repos/python/app/service.py"),
        ("javascript", "tests/fixtures/boundary_ir/repos/javascript/service.js"),
    ):
        source = (ROOT / fixture).read_bytes()
        tree = get_parser(language).parse(source)
        assert not tree.root_node.has_error
        parsed[language] = {"root_type": tree.root_node.type, "bytes": len(source)}

    database = CompatibilityDatabase(tmp_path / "trends.db")
    now = time.time()
    for language, age_days, throughput, memory_delta in (
        ("python", 1, 20.0, 4.0),
        ("javascript", 1.5, 100.0, 99.0),
        ("python", 2, 10.0, 8.0),
        ("python", 45, 200.0, 80.0),
    ):
        database.store_test_result(
            GrammarTestResult(
                language=language,
                grammar_version="pinned",
                test_type="parse",
                success=True,
                duration=0.1,
                sample_results=[parsed[language]],
                performance_metrics={
                    "avg_throughput_lines_per_sec": throughput,
                    "memory_delta_mb": memory_delta,
                },
                timestamp=now - age_days * 24 * 60 * 60,
            )
        )

    assert database.get_performance_trends("python", days=30) == {
        "language": "python",
        "days_analyzed": 30,
        "data_points": 2,
        "throughput": {"average": 15.0, "median": 15.0, "trend": "improving"},
        "memory": {"average_delta": 6.0, "median_delta": 6.0, "trend": "improving"},
    }


@pytest.mark.parametrize(
    ("samples", "expected_trend"),
    [
        ([(10.0, 8.0)], "insufficient_data"),
        ([(10.0, 8.0), (10.0, 8.0)], "stable"),
        ([(10.0, 8.0), (20.0, 4.0)], "improving"),
        ([(20.0, 4.0), (10.0, 8.0)], "declining"),
    ],
)
def test_performance_trends_distinguish_single_stable_and_directional_samples(
    tmp_path: Path,
    samples: list[tuple[float, float]],
    expected_trend: str,
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    tree = get_parser("python").parse(source)
    assert not tree.root_node.has_error

    database_path = tmp_path / "trends.db"
    database = CompatibilityDatabase(database_path)
    now = time.time()
    for index, (throughput, memory_delta) in enumerate(samples):
        database.store_test_result(
            GrammarTestResult(
                language="python",
                grammar_version="pinned",
                test_type="parse",
                success=True,
                duration=0.1,
                sample_results=[{"root_type": tree.root_node.type}],
                performance_metrics={
                    "avg_throughput_lines_per_sec": throughput,
                    "memory_delta_mb": memory_delta,
                },
                timestamp=now - (len(samples) - index) * 3600,
            )
        )

    trends = CompatibilityDatabase(database_path).get_performance_trends("python")
    assert trends["data_points"] == len(samples)
    assert trends["throughput"]["trend"] == expected_trend
    assert trends["memory"]["trend"] == expected_trend


def test_database_stats_count_persisted_parse_records_and_date_span(
    tmp_path: Path,
) -> None:
    parsed = {}
    for language, fixture in (
        ("python", "tests/fixtures/boundary_ir/repos/python/app/service.py"),
        ("javascript", "tests/fixtures/boundary_ir/repos/javascript/service.js"),
    ):
        source = (ROOT / fixture).read_bytes()
        tree = get_parser(language).parse(source)
        assert not tree.root_node.has_error
        parsed[language] = {"root_type": tree.root_node.type, "bytes": len(source)}

    database_path = tmp_path / "stats.db"
    database = CompatibilityDatabase(database_path)
    now = time.time()
    oldest = now - 3 * 24 * 60 * 60
    newest = now - 24 * 60 * 60
    for language, timestamp in (("python", oldest), ("javascript", newest)):
        database.store_compatibility_result(
            CompatibilityResult(
                language=language,
                grammar_version="pinned",
                language_version=None,
                level=CompatibilityLevel.COMPATIBLE,
                score=1.0,
                test_results={"parsed": parsed[language]},
                timestamp=timestamp,
            )
        )
    database.store_test_result(
        GrammarTestResult(
            language="python",
            grammar_version="pinned",
            test_type="parse",
            success=True,
            duration=0.1,
            sample_results=[parsed["python"]],
            timestamp=now,
        )
    )

    stats = CompatibilityDatabase(database_path).get_database_stats()
    assert stats["compatibility_results"] == 2
    assert stats["test_results"] == 1
    assert stats["grammar_metadata"] == 0
    assert stats["database_size_mb"] > 0
    assert stats["oldest_record"] == oldest
    assert stats["newest_record"] == newest
    assert stats["data_span_days"] == pytest.approx(2)


def test_database_cleanup_removes_old_records_and_preserves_recent_parses(
    tmp_path: Path,
) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    parser = get_parser("python")
    assert not parser.parse(source).root_node.has_error

    database = CompatibilityDatabase(tmp_path / "cleanup.db")
    now = time.time()
    for version, age_days, throughput in (
        ("old", 45, 10.0),
        ("recent", 1, 20.0),
    ):
        timestamp = now - age_days * 24 * 60 * 60
        database.store_compatibility_result(
            CompatibilityResult(
                language="python",
                grammar_version=version,
                language_version=None,
                level=CompatibilityLevel.COMPATIBLE,
                score=1.0,
                test_results={"parsed_bytes": len(source)},
                timestamp=timestamp,
            )
        )
        database.store_test_result(
            GrammarTestResult(
                language="python",
                grammar_version=version,
                test_type="parse",
                success=True,
                duration=0.1,
                sample_results=[{"parsed_bytes": len(source)}],
                performance_metrics={"avg_throughput_lines_per_sec": throughput},
                timestamp=timestamp,
            )
        )

    before = database.get_database_stats()
    assert before["compatibility_results"] == 2
    assert before["test_results"] == 2
    assert database.cleanup_old_data(days_to_keep=30) == {
        "compatibility_results": 1,
        "test_results": 1,
    }

    reopened = CompatibilityDatabase(database.database_path)
    assert reopened.get_compatibility_result("python", "old") is None
    recent = reopened.get_compatibility_result("python", "recent")
    assert recent is not None
    assert recent.test_results == {"parsed_bytes": len(source)}
    after = reopened.get_database_stats()
    assert after["compatibility_results"] == 1
    assert after["test_results"] == 1
    trends = reopened.get_performance_trends("python", days=30)
    assert trends["data_points"] == 1
    assert trends["throughput"]["average"] == 20.0
    assert not parser.parse(source).root_node.has_error
