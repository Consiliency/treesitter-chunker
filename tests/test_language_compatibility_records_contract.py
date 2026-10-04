"""Language constraints and persisted rules keep grammar selection stable."""

import json
import os
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from threading import Timer
from types import SimpleNamespace

import pytest

from chunker import get_parser
from chunker.languages.compatibility import database as database_module
from chunker.languages.compatibility.database import CompatibilityDatabase
from chunker.languages.compatibility.schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    GrammarVersion,
    LanguageVersion,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_constraints_and_rules_survive_sqlite_reopen(tmp_path: Path) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    below = LanguageVersion("python", "3.9")
    selected = LanguageVersion("python", "3.11", features=["match"])
    above = LanguageVersion("python", "3.13")
    grammar = GrammarVersion(
        "python",
        "1.0",
        "python.so",
        supported_features=["match"],
        min_language_version="3.10",
        max_language_version="3.12",
    )
    assert not grammar.supports_language_version(below)
    assert grammar.supports_language_version(selected)
    assert not grammar.supports_language_version(above)

    other_language = LanguageVersion("javascript", "3.11")
    other_grammar = GrammarVersion("javascript", "1.0", "javascript.so")
    rule = CompatibilityRule(
        "python", ">=3.10", "1.0", CompatibilityLevel.PARTIALLY_COMPATIBLE
    )
    db_path = tmp_path / "compatibility.db"
    with CompatibilityDatabase(db_path) as db:
        assert db.add_language_version(selected)
        assert db.add_grammar_version(grammar)
        assert db.add_language_version(other_language)
        assert db.add_grammar_version(other_grammar)
        assert db.add_compatibility_rule(rule)
        assert db.find_compatible_grammar(selected) == grammar
        assert db.find_compatible_grammar(other_language) == other_grammar
        assert db.get_compatibility_level(selected, grammar) == (
            CompatibilityLevel.PARTIALLY_COMPATIBLE
        )

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.get_language_versions("python") == [selected]
        assert reopened.get_grammar_versions("python") == [grammar]
        assert reopened.get_language_versions("javascript") == [other_language]
        assert reopened.find_compatible_grammar(selected) == grammar
        assert reopened.find_compatible_grammar(other_language) == other_grammar
        assert reopened.get_compatibility_level(selected, grammar) == (
            CompatibilityLevel.PARTIALLY_COMPATIBLE
        )
        assert reopened.get_compatibility_level(other_language, grammar) == (
            CompatibilityLevel.INCOMPATIBLE
        )


def test_backup_keeps_persisted_selection_and_live_database_usable(
    tmp_path: Path,
) -> None:
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error

    language = LanguageVersion("python", "3.11")
    grammar = GrammarVersion("python", "1.0", "python.so")
    db_path = tmp_path / "compatibility.db"
    backup_path = tmp_path / "backup.db"

    with CompatibilityDatabase(db_path) as database:
        assert database.add_language_version(language)
        assert database.add_grammar_version(grammar)
        assert database.find_compatible_grammar(language) == grammar
        database.backup_database(backup_path)
        assert backup_path.is_file()
        assert database.find_compatible_grammar(language) == grammar
        assert database.add_language_version(LanguageVersion("rust", "2021"))

    with CompatibilityDatabase(backup_path) as backup:
        assert backup.get_language_versions("python") == [language]
        assert backup.find_compatible_grammar(language) == grammar
        assert backup.get_language_versions("rust") == []

    with CompatibilityDatabase(db_path) as current:
        assert current.get_language_versions("rust") == [
            LanguageVersion("rust", "2021")
        ]
        with pytest.raises(FileNotFoundError):
            current.restore_database(tmp_path / "missing.db")
        assert current.find_compatible_grammar(language) == grammar

        current.restore_database(backup_path)
        assert current.get_language_versions("python") == [language]
        assert current.get_language_versions("rust") == []
        assert current.find_compatible_grammar(language) == grammar
        assert current.add_language_version(LanguageVersion("go", "1.22"))
        assert current.get_language_versions("go") == [LanguageVersion("go", "1.22")]


def test_backup_includes_committed_wal_records_with_live_reader(tmp_path: Path) -> None:
    db_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    language = LanguageVersion("python", "3.11")
    with CompatibilityDatabase(db_path) as live:
        assert live.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert live.add_language_version(language)
        with closing(sqlite3.connect(db_path)) as reader:
            reader.execute("BEGIN")
            assert (
                reader.execute("SELECT COUNT(*) FROM language_versions").fetchone()[0]
                == 1
            )
            live.backup_database(backup_path)
            assert live.get_language_versions("python") == [language]

    with CompatibilityDatabase(backup_path) as backup:
        assert backup.get_language_versions("python") == [language]


def test_backup_rejects_active_transaction_and_source_path(tmp_path: Path) -> None:
    db_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    with CompatibilityDatabase(db_path) as live:
        with pytest.raises(shutil.SameFileError):
            live.backup_database(db_path)
        live.conn.execute("BEGIN")
        try:
            with pytest.raises(sqlite3.OperationalError, match="transaction is active"):
                live.backup_database(backup_path)
            assert not backup_path.exists()
        finally:
            live.conn.rollback()


def test_backup_rejects_hard_link_to_source(tmp_path: Path) -> None:
    db_path = tmp_path / "live.db"
    linked_path = tmp_path / "linked.db"
    with CompatibilityDatabase(db_path) as live:
        try:
            os.link(db_path, linked_path)
        except OSError:
            pytest.skip("File hard links are unavailable on this host")
        with pytest.raises(shutil.SameFileError):
            live.backup_database(linked_path)


@pytest.mark.parametrize("journal_mode", ["delete", "wal"])
def test_backup_fails_in_bounded_time_when_destination_reader_blocks(
    tmp_path: Path,
    journal_mode: str,
) -> None:
    db_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    with CompatibilityDatabase(db_path) as live:
        assert live.add_language_version(LanguageVersion("python", "3.11"))
        with closing(sqlite3.connect(backup_path)) as destination:
            destination.execute("CREATE TABLE marker (value INTEGER)")
            destination.execute("INSERT INTO marker VALUES (1)")
            destination.commit()
            assert (
                destination.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0]
                == journal_mode
            )
        with closing(sqlite3.connect(backup_path)) as reader:
            reader.execute("BEGIN")
            assert reader.execute("SELECT value FROM marker").fetchone()[0] == 1
            started = time.monotonic()
            with pytest.raises(sqlite3.OperationalError, match="Backup blocked"):
                live.backup_database(backup_path)
            assert time.monotonic() - started < 5
            assert live.get_language_versions("python") == [
                LanguageVersion("python", "3.11")
            ]
        with closing(sqlite3.connect(backup_path)) as destination:
            assert destination.execute("SELECT value FROM marker").fetchone()[0] == 1


def test_backup_over_existing_wal_destination_restores_current_data(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"
    language = LanguageVersion("python", "3.11")
    with CompatibilityDatabase(db_path) as live:
        assert live.add_language_version(language)
        with CompatibilityDatabase(backup_path) as old_backup:
            assert (
                old_backup.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                == "wal"
            )
            assert old_backup.add_language_version(LanguageVersion("rust", "2021"))
        live.backup_database(backup_path)

    with CompatibilityDatabase(restored_path) as restored:
        restored.restore_database(backup_path)
        assert restored.get_language_versions("python") == [language]
        assert restored.get_language_versions("rust") == []


def test_export_import_preserves_language_grammar_rules_and_breaking_changes(
    tmp_path: Path,
) -> None:
    for language, fixture in (
        ("python", FIXTURE),
        (
            "javascript",
            Path(__file__).resolve().parents[1]
            / "tests/fixtures/boundary_ir/repos/javascript/service.js",
        ),
    ):
        assert not get_parser(language).parse(fixture.read_bytes()).root_node.has_error

    python = LanguageVersion("python", "3.11", features=["match"])
    javascript = LanguageVersion("javascript", "2023")
    python_grammar = GrammarVersion(
        "python", "1.0", "python.so", supported_features=["match"]
    )
    javascript_grammar = GrammarVersion("javascript", "1.0", "javascript.so")
    rule = CompatibilityRule(
        "python", ">=3.10", "1.0", CompatibilityLevel.PARTIALLY_COMPATIBLE
    )
    breaking = BreakingChange(
        "python", "0.9", "1.0", "syntax", "Changed pattern syntax", "medium"
    )
    export_path = tmp_path / "compatibility.json"
    with CompatibilityDatabase(tmp_path / "source.db") as source:
        for language_version in (python, javascript):
            assert source.add_language_version(language_version)
        for grammar_version in (python_grammar, javascript_grammar):
            assert source.add_grammar_version(grammar_version)
        assert source.add_compatibility_rule(rule)
        assert source.add_breaking_change(breaking)
        source.export_database(export_path)

    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert {entry["language"] for entry in exported["language_versions"]} == {
        "python",
        "javascript",
    }
    assert len(exported["grammar_versions"]) == 2
    assert exported["compatibility_rules"][0]["compatibility_level"] == (
        "partially_compatible"
    )
    assert exported["breaking_changes"][0]["description"] == ("Changed pattern syntax")

    destination_path = tmp_path / "destination.db"
    old_language = LanguageVersion("rust", "2021", features=["edition2021"])
    old_grammar = GrammarVersion(
        "rust", "1.0", "rust.so", supported_features=["edition2021"]
    )
    old_rule = CompatibilityRule(
        "rust", ">=2021", "1.0", CompatibilityLevel.INCOMPATIBLE
    )
    old_breaking = BreakingChange(
        "rust", "0.9", "1.0", "syntax", "Old Rust syntax", "high"
    )
    with CompatibilityDatabase(destination_path) as destination:
        assert destination.add_language_version(old_language)
        assert destination.add_grammar_version(old_grammar)
        assert destination.add_compatibility_rule(old_rule)
        assert destination.add_breaking_change(old_breaking)
        destination.import_database(export_path)

    with CompatibilityDatabase(destination_path) as reopened:
        assert reopened.get_language_versions("python") == [python]
        assert reopened.get_language_versions("javascript") == [javascript]
        assert reopened.get_language_versions("rust") == []
        assert reopened.get_grammar_versions("rust") == []
        assert reopened.get_compatibility_level(old_language, old_grammar) == (
            CompatibilityLevel.FULLY_COMPATIBLE
        )
        assert reopened.get_breaking_changes("rust", "0.9", "1.0") == []
        assert reopened.get_grammar_versions("python") == [python_grammar]
        assert reopened.get_grammar_versions("javascript") == [javascript_grammar]
        assert reopened.get_compatibility_level(python, python_grammar) == (
            CompatibilityLevel.PARTIALLY_COMPATIBLE
        )
        assert reopened.get_breaking_changes("python", "0.9", "1.0") == [breaking]


def test_import_refreshes_live_selection_and_rolls_back_invalid_schema(
    tmp_path: Path,
) -> None:
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    language = LanguageVersion("python", "3.11", features=["match"])
    grammar = GrammarVersion("python", "1.0", "python.so", supported_features=["match"])
    rule = CompatibilityRule(
        "python", ">=3.10", "1.0", CompatibilityLevel.PARTIALLY_COMPATIBLE
    )
    export_path = tmp_path / "valid.json"
    with CompatibilityDatabase(tmp_path / "source.db") as source:
        assert source.add_language_version(language)
        assert source.add_grammar_version(grammar)
        assert source.add_compatibility_rule(rule)
        source.export_database(export_path)

    invalid = json.loads(export_path.read_text(encoding="utf-8"))
    invalid["compatibility_rules"][0]["compatibility_level"] = "invalid"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    incomplete_path = tmp_path / "incomplete.json"
    incomplete_path.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

    destination_path = tmp_path / "destination.db"
    with CompatibilityDatabase(destination_path) as destination:
        assert destination.add_language_version(LanguageVersion("rust", "2021"))
        destination.import_database(export_path)
        assert destination.get_language_versions("rust") == []
        assert destination.find_compatible_grammar(language) == grammar
        assert destination.get_compatibility_level(language, grammar) == (
            CompatibilityLevel.PARTIALLY_COMPATIBLE
        )

        for malformed_path in (invalid_path, incomplete_path):
            with pytest.raises(ValueError):
                destination.import_database(malformed_path)
            assert destination.get_language_versions("python") == [language]
            assert destination.find_compatible_grammar(language) == grammar
            assert destination.get_compatibility_level(language, grammar) == (
                CompatibilityLevel.PARTIALLY_COMPATIBLE
            )

    with CompatibilityDatabase(destination_path) as reopened:
        assert reopened.get_language_versions("python") == [language]
        assert reopened.find_compatible_grammar(language) == grammar


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("language_versions", "features", "null"),
        ("grammar_versions", "supported_features", "42"),
        ("grammar_versions", "breaking_changes", "[{}]"),
        ("breaking_changes", "affected_features", "null"),
    ],
)
def test_import_rejects_invalid_feature_lists_without_replacing_live_records(
    tmp_path: Path, table: str, column: str, value: str
) -> None:
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    export_path = tmp_path / "valid.json"
    language = LanguageVersion("python", "3.11")
    grammar = GrammarVersion("python", "1.0", "python.so")
    with CompatibilityDatabase(tmp_path / "source.db") as source:
        assert source.add_language_version(language)
        assert source.add_grammar_version(grammar)
        assert source.add_breaking_change(
            BreakingChange("python", "0.9", "1.0", "syntax", "change", "medium")
        )
        source.export_database(export_path)

    invalid = json.loads(export_path.read_text(encoding="utf-8"))
    invalid[table][0][column] = value
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    db_path = tmp_path / "live.db"
    live_language = LanguageVersion("rust", "2021")
    live_grammar = GrammarVersion("rust", "1.0", "rust.so")
    with CompatibilityDatabase(db_path) as live:
        assert live.add_language_version(live_language)
        assert live.add_grammar_version(live_grammar)
        with pytest.raises(ValueError, match="list of strings"):
            live.import_database(invalid_path)
        assert live.find_compatible_grammar(live_language) == live_grammar

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.find_compatible_grammar(live_language) == live_grammar
        assert reopened.get_language_versions("python") == []


def test_restore_rejects_invalid_backup_without_replacing_live_database(
    tmp_path: Path,
) -> None:
    assert not get_parser("python").parse(FIXTURE.read_bytes()).root_node.has_error
    backup_path = tmp_path / "backup.db"
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(LanguageVersion("python", "3.11"))
        assert backup.add_grammar_version(GrammarVersion("python", "1.0", "python.so"))
    with closing(sqlite3.connect(backup_path)) as conn:
        conn.execute("UPDATE grammar_versions SET supported_features = 'null'")
        conn.commit()

    db_path = tmp_path / "live.db"
    live_language = LanguageVersion("rust", "2021")
    live_grammar = GrammarVersion("rust", "1.0", "rust.so")
    with CompatibilityDatabase(db_path) as live:
        assert live.add_language_version(live_language)
        assert live.add_grammar_version(live_grammar)
        original_bytes = db_path.read_bytes()
        with pytest.raises(ValueError, match="list of strings"):
            live.restore_database(backup_path)
        assert db_path.read_bytes() == original_bytes
        assert live.find_compatible_grammar(live_language) == live_grammar

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.find_compatible_grammar(live_language) == live_grammar


def test_restore_through_symlink_updates_target_without_replacing_link(
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "backup.db"
    language = LanguageVersion("python", "3.11")
    grammar = GrammarVersion("python", "1.0", "python.so")
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(language)
        assert backup.add_grammar_version(grammar)

    target_path = tmp_path / "target.db"
    with CompatibilityDatabase(target_path) as target:
        assert target.add_language_version(LanguageVersion("rust", "2021"))
    alias_path = tmp_path / "alias.db"
    try:
        alias_path.symlink_to(target_path)
    except OSError:
        pytest.skip("File symlinks are unavailable on this host")

    with CompatibilityDatabase(alias_path) as live:
        live.restore_database(backup_path)
        assert alias_path.is_symlink()
        assert live.find_compatible_grammar(language) == grammar

    with CompatibilityDatabase(target_path) as reopened:
        assert reopened.find_compatible_grammar(language) == grammar
        assert reopened.get_language_versions("rust") == []


def test_restore_with_live_wal_keeps_disk_and_schema_consistent(
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "backup.db"
    language = LanguageVersion("python", "3.11")
    grammar = GrammarVersion("python", "1.0", "python.so")
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(language)
        assert backup.add_grammar_version(grammar)

    db_path = tmp_path / "live.db"
    with CompatibilityDatabase(db_path) as live:
        assert live.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert live.add_language_version(LanguageVersion("rust", "2021"))
        with closing(sqlite3.connect(db_path)) as observer:
            observer.execute("BEGIN")
            assert (
                observer.execute("SELECT COUNT(*) FROM language_versions").fetchone()[0]
                == 1
            )
            live.restore_database(backup_path)
            assert live.find_compatible_grammar(language) == grammar
            assert live.get_language_versions("python") == [language]

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.find_compatible_grammar(language) == grammar
        assert reopened.get_language_versions("rust") == []


def test_restore_with_live_wal_accepts_different_backup_page_size(
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "backup.db"
    with closing(sqlite3.connect(backup_path)) as conn:
        conn.execute("PRAGMA page_size=8192")
        conn.execute("VACUUM")
    language = LanguageVersion("python", "3.11")
    grammar = GrammarVersion("python", "1.0", "python.so")
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.conn.execute("PRAGMA page_size").fetchone()[0] == 8192
        assert backup.add_language_version(language)
        assert backup.add_grammar_version(grammar)

    db_path = tmp_path / "live.db"
    with CompatibilityDatabase(db_path) as live:
        assert live.conn.execute("PRAGMA page_size").fetchone()[0] == 4096
        assert live.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert live.add_language_version(LanguageVersion("rust", "2021"))
        live.restore_database(backup_path)
        assert live.find_compatible_grammar(language) == grammar
        assert live.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.conn.execute("PRAGMA page_size").fetchone()[0] == 8192
        assert reopened.find_compatible_grammar(language) == grammar
        assert reopened.get_language_versions("rust") == []


def test_restore_fails_in_bounded_time_when_reader_blocks_default_journal(
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "backup.db"
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(LanguageVersion("python", "3.11"))

    db_path = tmp_path / "live.db"
    live_language = LanguageVersion("rust", "2021")
    with CompatibilityDatabase(db_path) as live:
        assert live.add_language_version(live_language)
        reader = sqlite3.connect(db_path, check_same_thread=False)
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM language_versions").fetchone()
        release_reader = Timer(6, reader.close)
        release_reader.daemon = True
        release_reader.start()
        try:
            started = time.monotonic()
            with pytest.raises(sqlite3.OperationalError, match="blocked"):
                live.restore_database(backup_path)
            assert time.monotonic() - started < 5
            assert live.get_language_versions("rust") == [live_language]
            assert live.get_language_versions("python") == []
        finally:
            release_reader.cancel()
            reader.close()


def test_restore_keeps_schema_current_if_wal_reenable_is_blocked(
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "backup.db"
    with closing(sqlite3.connect(backup_path)) as conn:
        conn.execute("PRAGMA page_size=8192")
        conn.execute("VACUUM")
    language = LanguageVersion("python", "3.11")
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(language)

    db_path = tmp_path / "live.db"
    readers: list[sqlite3.Connection] = []
    with CompatibilityDatabase(db_path) as live:
        assert live.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert live.add_language_version(LanguageVersion("rust", "2021"))
        live.conn.execute("PRAGMA busy_timeout=200")

        def hold_read_lock(statement: str) -> None:
            if statement == "PRAGMA journal_mode=WAL":
                reader = sqlite3.connect(db_path)
                reader.execute("BEGIN")
                reader.execute("SELECT COUNT(*) FROM language_versions").fetchone()
                readers.append(reader)

        live.conn.set_trace_callback(hold_read_lock)
        try:
            with pytest.raises(sqlite3.OperationalError, match="Database restored"):
                live.restore_database(backup_path)
            assert live.get_language_versions("python") == [language]
            assert live.get_language_versions("rust") == []
            assert live.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 200
        finally:
            live.conn.set_trace_callback(None)
            for reader in readers:
                reader.close()

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.get_language_versions("python") == [language]


def test_restore_reports_wal_mode_change_when_backup_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_path = tmp_path / "backup.db"
    with closing(sqlite3.connect(backup_path)) as conn:
        conn.execute("PRAGMA page_size=8192")
        conn.execute("VACUUM")
    with CompatibilityDatabase(backup_path) as backup:
        assert backup.add_language_version(LanguageVersion("python", "3.11"))

    db_path = tmp_path / "live.db"
    live_language = LanguageVersion("rust", "2021")
    readers: list[sqlite3.Connection] = []
    real_monotonic = time.monotonic

    def start_reader_after_mode_switch() -> float:
        if not readers:
            reader = sqlite3.connect(db_path)
            reader.execute("BEGIN")
            reader.execute("SELECT COUNT(*) FROM language_versions").fetchone()
            readers.append(reader)
        return real_monotonic()

    with CompatibilityDatabase(db_path) as live:
        assert live.conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert live.add_language_version(live_language)
        monkeypatch.setattr(
            database_module,
            "time",
            SimpleNamespace(monotonic=start_reader_after_mode_switch),
        )
        try:
            with pytest.raises(
                sqlite3.OperationalError,
                match="Restore failed and WAL journal mode could not be restored",
            ):
                live.restore_database(backup_path)
            assert live.get_language_versions("rust") == [live_language]
            assert live.get_language_versions("python") == []
            assert live.conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        finally:
            for reader in readers:
                reader.close()
