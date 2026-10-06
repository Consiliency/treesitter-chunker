"""Canonical compatibility versions and preserved legacy SQLite records."""

import gc
import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import asdict, replace
from pathlib import Path

import psutil
import pytest

from chunker import get_parser
from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    CompatibilityLevel,
    CompatibilityResult,
)
from chunker.grammar_management.core import (
    GrammarManager,
    GrammarValidator,
    load_compiled_grammar,
)


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCHEMA = """
CREATE TABLE compatibility_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL,
    grammar_version TEXT NOT NULL, language_version TEXT,
    level TEXT NOT NULL, score REAL NOT NULL, issues TEXT, warnings TEXT,
    breaking_changes TEXT, performance_impact TEXT, test_results TEXT,
    timestamp REAL NOT NULL,
    UNIQUE(language, grammar_version, language_version)
);
"""


@pytest.fixture
def parsed_results():
    source = (
        ROOT / "tests/fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    parser = get_parser("python")
    accepted = parser.parse(source)
    rejected = parser.parse(source + b"\ndef broken(\n")
    assert not accepted.root_node.has_error
    assert rejected.root_node.has_error
    results = []
    for tree in (accepted, rejected):
        failed = tree.root_node.has_error
        results.append(
            CompatibilityResult(
                "python",
                "fixture",
                None,
                (
                    CompatibilityLevel.INCOMPATIBLE
                    if failed
                    else CompatibilityLevel.COMPATIBLE
                ),
                score=0.0 if failed else 1.0,
                issues=["Actual fixture parse failed"] if failed else [],
                warnings=["Legacy observation"],
                breaking_changes=[{"parse_failed": failed}],
                performance_impact={"average_parse_time": 0.02},
                test_results={
                    "root_type": tree.root_node.type,
                    "success_rate": float(not failed),
                },
            )
        )
    return results


def test_unspecified_and_concrete_writes_replace_only_their_key(
    tmp_path, parsed_results
):
    valid, invalid = parsed_results
    invalid = replace(invalid, timestamp=valid.timestamp - 100)
    path = tmp_path / "history.db"
    database = CompatibilityDatabase(path)
    other = replace(valid, grammar_version="other")
    concrete = replace(invalid, language_version="3.13")
    for result in (
        valid,
        invalid,
        replace(valid, language_version="3.13"),
        concrete,
        other,
    ):
        database.store_compatibility_result(result)
    with closing(sqlite3.connect(path)) as connection:
        counts = connection.execute(
            "SELECT grammar_version, language_version, COUNT(*) "
            "FROM compatibility_results GROUP BY grammar_version, language_version"
        ).fetchall()
    assert counts == [("fixture", None, 1), ("fixture", "3.13", 1), ("other", None, 1)]
    reopened = CompatibilityDatabase(path)
    assert asdict(reopened.get_compatibility_result("python", "fixture")) == asdict(
        invalid
    )
    assert asdict(
        reopened.get_compatibility_result("python", "fixture", "3.13")
    ) == asdict(concrete)
    assert asdict(reopened.get_compatibility_result("python", "other")) == asdict(other)


def test_exact_version_precedes_newer_truthful_fallback(tmp_path, parsed_results):
    valid, invalid = parsed_results
    path = tmp_path / "lookup.db"
    database = CompatibilityDatabase(path)
    exact = replace(invalid, language_version="3.13", timestamp=time.time() - 100)
    fallback = replace(valid, timestamp=time.time() - 10)
    database.store_compatibility_result(exact)
    database.store_compatibility_result(fallback)
    reopened = CompatibilityDatabase(path)
    assert asdict(
        reopened.get_compatibility_result("python", "fixture", "3.13")
    ) == asdict(exact)
    assert asdict(
        reopened.get_compatibility_result("python", "fixture", "3.14")
    ) == asdict(fallback)
    assert asdict(reopened.get_compatibility_result("python", "fixture")) == asdict(
        fallback
    )
    assert reopened.get_compatibility_result("python", "missing", "3.13") is None
    assert reopened.get_compatibility_result("missing", "fixture", "3.13") is None


@pytest.fixture
def legacy_database(tmp_path, parsed_results):
    path = tmp_path / "legacy.db"
    valid, invalid = parsed_results
    now = time.time()
    observations = [
        replace(valid, timestamp=now - 100 * 86400),
        replace(invalid, timestamp=now - 10),
        replace(valid, timestamp=now - 50),
        replace(valid, timestamp=now - 10),
        replace(invalid, language_version="3.13", timestamp=now - 100),
        replace(valid, grammar_version="old", timestamp=now - 100 * 86400),
    ]
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(LEGACY_SCHEMA)
        for result in observations:
            connection.execute(
                "INSERT INTO compatibility_results "
                "(language, grammar_version, language_version, level, score, issues, "
                "warnings, breaking_changes, performance_impact, test_results, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.language,
                    result.grammar_version,
                    result.language_version,
                    result.level.value,
                    result.score,
                    json.dumps(result.issues),
                    json.dumps(result.warnings),
                    json.dumps(result.breaking_changes),
                    json.dumps(result.performance_impact),
                    json.dumps(result.test_results),
                    result.timestamp,
                ),
            )
        rows = connection.execute(
            "SELECT * FROM compatibility_results ORDER BY id"
        ).fetchall()
    return path, rows


def test_legacy_migration_preserves_complete_rows_and_canonical_retention(
    legacy_database,
):
    path, original = legacy_database
    expected_archive = original[:3]
    expected_canonical = original[3:]
    database = CompatibilityDatabase(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        canonical = connection.execute(
            "SELECT * FROM compatibility_results ORDER BY id"
        ).fetchall()
        archive = connection.execute(
            "SELECT * FROM compatibility_results_null_archive ORDER BY id"
        ).fetchall()
        connection.execute(
            "INSERT INTO grammar_metadata (language, metadata) VALUES (?, ?)",
            ("python", json.dumps({"root_type": "module"})),
        )
        connection.execute(
            "INSERT INTO test_results (language, grammar_version, test_type, success, duration, timestamp) "
            "VALUES ('python', 'fixture', 'parse', 1, 0.01, ?)",
            (time.time() - 100 * 86400,),
        )
    assert canonical == expected_canonical
    assert archive == expected_archive
    assert len(database.get_compatibility_history("python")) == 3
    stats = database.get_database_stats()
    assert stats["compatibility_results"] == 3
    assert stats["oldest_record"] == min(row[-1] for row in expected_canonical)
    assert stats["newest_record"] == max(row[-1] for row in expected_canonical)
    assert database.cleanup_old_data(days_to_keep=90) == {
        "compatibility_results": 1,
        "test_results": 1,
    }
    reopened = CompatibilityDatabase(path)
    retained = reopened.get_compatibility_result("python", "fixture")
    assert retained.timestamp == original[3][-1]
    reopened.store_compatibility_result(replace(retained, timestamp=time.time() - 1000))
    CompatibilityDatabase(path)
    with closing(sqlite3.connect(path)) as connection:
        assert (
            connection.execute(
                "SELECT * FROM compatibility_results_null_archive ORDER BY id"
            ).fetchall()
            == expected_archive
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM compatibility_results"
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT metadata FROM grammar_metadata"
        ).fetchone() == (json.dumps({"root_type": "module"}),)
        assert connection.execute("SELECT COUNT(*) FROM test_results").fetchone() == (
            0,
        )


def test_database_constraint_rejects_second_unspecified_row(legacy_database):
    path, _ = legacy_database
    CompatibilityDatabase(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO compatibility_results (language, grammar_version, language_version, level, score, timestamp) "
                "VALUES ('python', 'fixture', NULL, 'compatible', 1, ?)",
                (time.time(),),
            )


def test_failed_migration_rolls_back_archive_and_closes_handles(legacy_database):
    path, original = legacy_database
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TRIGGER deny_migration BEFORE DELETE ON compatibility_results "
            "BEGIN SELECT RAISE(ABORT, 'migration denied'); END"
        )
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="migration denied"):
            CompatibilityDatabase(path)
        assert not any(
            Path(file.path).resolve() == path.resolve()
            for file in psutil.Process().open_files()
        )
        with closing(sqlite3.connect(path)) as connection, connection:
            assert (
                connection.execute(
                    "SELECT * FROM compatibility_results ORDER BY id"
                ).fetchall()
                == original
            )
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name IN "
                    "('compatibility_results_null_archive', 'idx_compatibility_null_version')"
                ).fetchall()
                == []
            )
            connection.execute("DROP TRIGGER deny_migration")
        CompatibilityDatabase(path)
        with closing(sqlite3.connect(path)) as connection:
            assert (
                connection.execute(
                    "SELECT * FROM compatibility_results_null_archive ORDER BY id"
                ).fetchall()
                == original[:3]
            )
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def test_migrated_reopen_does_not_acquire_writer_lock(tmp_path):
    path = tmp_path / "reopen.db"
    CompatibilityDatabase(path)
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        reopened = CompatibilityDatabase(path)
        assert reopened.get_compatibility_history("python") == []
        writer.rollback()


@pytest.mark.skipif(sys.platform != "linux", reason="Known BAML fixture uses Linux cc")
def test_concrete_checker_evaluates_instead_of_reusing_unspecified_result(
    tmp_path, monkeypatch
):
    source = (
        ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
    ).read_text(encoding="utf-8")
    parser = get_parser("baml")
    assert not parser.parse(source.encode()).root_node.has_error
    assert parser.parse((source + "\nclass Broken {").encode()).root_node.has_error
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    user = tmp_path / "user"
    user.mkdir()
    library = user / "libbaml.so"
    grammar_source = ROOT / "packages/baml-grammar/src"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(grammar_source),
            str(grammar_source / "parser.c"),
            "-o",
            str(library),
        ],
        check=True,
    )
    assert (
        not load_compiled_grammar(library, "baml")
        .parse(source.encode())
        .root_node.has_error
    )
    manager = GrammarManager(
        user_dir=user, package_dir=tmp_path / "package", cache_dir=tmp_path / "cache"
    )
    path = tmp_path / "checker.db"
    database = CompatibilityDatabase(path)
    fallback = CompatibilityResult(
        "baml",
        "unknown",
        None,
        CompatibilityLevel.INCOMPATIBLE,
        score=0.0,
        issues=["Real malformed BAML parse"],
        test_results={"successful_samples": 0, "success_rate": 0.0},
    )
    database.store_compatibility_result(fallback)
    checker = CompatibilityChecker(
        manager, database, GrammarValidator(tmp_path / "validation")
    )
    concrete = checker.check_compatibility("baml", "unknown", "requested", [source])
    assert concrete.language_version == "requested"
    assert concrete.level != CompatibilityLevel.INCOMPATIBLE
    assert concrete.score > 0.0
    assert concrete.test_results["successful_samples"] == 1
    reopened = CompatibilityDatabase(path)
    assert asdict(
        reopened.get_compatibility_result("baml", "unknown", "requested")
    ) == asdict(concrete)
    assert asdict(reopened.get_compatibility_result("baml", "unknown")) == asdict(
        fallback
    )
    assert asdict(
        CompatibilityChecker(manager, reopened).check_compatibility("baml", "unknown")
    ) == asdict(fallback)
    assert not (home / ".cache" / "treesitter-chunker").exists()
