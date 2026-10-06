"""Persisted grammar compatibility cleanup using parsed source fixtures."""

import gc
import sqlite3
import time
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import psutil
import pytest

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityDatabase,
    CompatibilityLevel,
    CompatibilityResult,
    TestResult as GrammarTestResult,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "operation",
    [
        "initialize",
        "store_compatibility",
        "get_compatibility",
        "store_test",
        "history",
        "trends",
        "cleanup",
        "stats",
        "failed_store",
        "failed_query",
        "failed_cleanup",
    ],
)
def test_database_operations_release_handles_without_gc(tmp_path, operation):
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    tree = get_parser("python").parse(source)
    assert tree.root_node.child_count > 0
    assert not tree.root_node.has_error
    path = tmp_path / "lifetime.db"
    database = CompatibilityDatabase(path)
    timestamp = time.time() - 100 * 24 * 60 * 60
    compatibility = CompatibilityResult(
        "python",
        "fixture",
        "3.13",
        CompatibilityLevel.COMPATIBLE,
        score=1.0,
        test_results={"parsed_bytes": len(source)},
        timestamp=timestamp,
    )
    parsed = GrammarTestResult(
        "python",
        "fixture",
        "parse",
        True,
        0.1,
        sample_results=[{"root_type": tree.root_node.type}],
        performance_metrics={"avg_throughput_lines_per_sec": 1.0},
    )
    database.store_compatibility_result(compatibility)
    database.store_test_result(parsed)
    if operation == "failed_query":
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("UPDATE compatibility_results SET issues = '{'")
    if operation == "failed_cleanup":
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("DROP TABLE test_results")
    calls = {
        "initialize": lambda: CompatibilityDatabase(path),
        "store_compatibility": lambda: database.store_compatibility_result(
            compatibility
        ),
        "get_compatibility": lambda: database.get_compatibility_result(
            "python", "fixture", "3.13"
        ),
        "store_test": lambda: database.store_test_result(parsed),
        "history": lambda: database.get_compatibility_history("python"),
        "trends": lambda: database.get_performance_trends("python"),
        "cleanup": database.cleanup_old_data,
        "stats": database.get_database_stats,
        "failed_store": lambda: database.store_compatibility_result(
            replace(compatibility, score=None)
        ),
        "failed_query": lambda: database.get_compatibility_result(
            "python", "fixture", "3.13"
        ),
        "failed_cleanup": database.cleanup_old_data,
    }
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        result = calls[operation]()
        assert not any(
            Path(file.path) == path for file in psutil.Process().open_files()
        ), "Database operation retained an open connection"
        with closing(sqlite3.connect(path)) as connection:
            rows = connection.execute(
                "SELECT grammar_version, score, test_results FROM compatibility_results"
            ).fetchall()
        if operation == "cleanup":
            assert result == {"compatibility_results": 1, "test_results": 0}
            assert rows == []
        else:
            assert len(rows) == 1
            assert rows[0][:2] == ("fixture", 1.0)
            assert "parsed_bytes" in rows[0][2]
        if operation in {"failed_store", "failed_query"}:
            assert result is None
        if operation == "get_compatibility":
            assert result == compatibility
        if operation == "history":
            assert result == [compatibility]
        if operation == "trends":
            assert result["data_points"] == 1
            assert result["throughput"]["average"] == 1.0
        if operation == "stats":
            assert result["compatibility_results"] == 1
            assert result["test_results"] == 1
            assert result["grammar_metadata"] == 0
        if operation == "failed_cleanup":
            assert "no such table" in result["error"]
        path.unlink()
        assert not path.exists()
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def test_database_initialization_failure_closes_connection(tmp_path):
    path = tmp_path / "invalid-schema.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE VIEW compatibility_results AS SELECT 1")
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        with pytest.raises(sqlite3.OperationalError, match="views may not be indexed"):
            CompatibilityDatabase(path)
        assert not any(
            Path(file.path) == path for file in psutil.Process().open_files()
        )
        path.unlink()
        assert not path.exists()
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def test_cleanup_removes_stale_records_and_keeps_recent_parses(tmp_path: Path) -> None:
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    tree = get_parser("python").parse(source)
    assert not tree.root_node.has_error
    parsed = {"root_type": tree.root_node.type, "bytes": len(source)}

    database_path = tmp_path / "compatibility.db"
    database = CompatibilityDatabase(database_path)
    now = time.time()
    for version, age_days in (("stale", 100), ("recent", 10)):
        timestamp = now - age_days * 24 * 60 * 60
        database.store_compatibility_result(
            CompatibilityResult(
                language="python",
                grammar_version=version,
                language_version=None,
                level=CompatibilityLevel.COMPATIBLE,
                score=1.0,
                test_results={"parsed": parsed},
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
                sample_results=[parsed],
                timestamp=timestamp,
            )
        )

    assert database.cleanup_old_data(days_to_keep=90) == {
        "compatibility_results": 1,
        "test_results": 1,
    }
    reopened = CompatibilityDatabase(database_path)
    stats = reopened.get_database_stats()
    assert stats["compatibility_results"] == 1
    assert stats["test_results"] == 1
    assert reopened.get_compatibility_result("python", "stale") is None
    assert reopened.get_compatibility_result("python", "recent") is not None
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT grammar_version FROM test_results").fetchall() == [
            ("recent",)
        ]
