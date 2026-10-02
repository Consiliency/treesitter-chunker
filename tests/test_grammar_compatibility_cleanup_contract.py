"""Persisted grammar compatibility cleanup using parsed source fixtures."""

import sqlite3
import time
from pathlib import Path

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityDatabase,
    CompatibilityLevel,
    CompatibilityResult,
    TestResult as GrammarTestResult,
)


ROOT = Path(__file__).resolve().parents[1]


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
