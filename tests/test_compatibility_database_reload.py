"""Persisted compatibility records restore selection after a cold open."""

from datetime import datetime
from pathlib import Path

import pytest

from chunker import get_parser

from chunker.languages.compatibility.database import CompatibilityDatabase
from chunker.languages.compatibility.schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    GrammarVersion,
    LanguageVersion,
)


def test_reopened_database_uses_persisted_grammar_rule_and_changes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compatibility.db"
    language = LanguageVersion("python", "3.11", features=["match"])
    grammar = GrammarVersion("python", "1.0", "python.so", max_language_version="3.10")
    other_language = LanguageVersion("javascript", "3.11")
    other_grammar = GrammarVersion("javascript", "1.0", "javascript.so")
    rule = CompatibilityRule(
        "python", ">=3.10", ">=1.0", CompatibilityLevel.FULLY_COMPATIBLE
    )
    change = BreakingChange(
        "python", "3.10", "3.11", "syntax", "Match statement", "medium"
    )

    with CompatibilityDatabase(db_path) as db:
        assert db.add_language_version(language)
        assert db.add_grammar_version(grammar)
        assert db.add_language_version(other_language)
        assert db.add_grammar_version(other_grammar)
        assert db.add_compatibility_rule(rule)
        assert db.add_breaking_change(change)
        assert db.find_compatible_grammar(language) == grammar
        assert db.find_compatible_grammar(other_language) == other_grammar

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.get_language_versions("python") == [language]
        assert reopened.get_grammar_versions("python") == [grammar]
        assert reopened.find_compatible_grammar(language) == grammar
        assert reopened.get_compatibility_level(language, grammar) == (
            CompatibilityLevel.FULLY_COMPATIBLE
        )
        assert reopened.find_compatible_grammar(other_language) == other_grammar
        assert reopened.schema.get_grammar_versions("javascript") == [other_grammar]
        assert reopened.schema.breaking_changes == [change]


def test_tied_grammar_selection_survives_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "ordered.db"
    language = LanguageVersion("python", "3.11")
    first = GrammarVersion("python", "2.0", "first.so")
    second = GrammarVersion("python", "1.0", "second.so")
    with CompatibilityDatabase(db_path) as db:
        assert db.add_language_version(language)
        assert db.add_grammar_version(first)
        assert db.add_grammar_version(second)
        assert db.find_compatible_grammar(language) == first

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.find_compatible_grammar(language) == first


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/python/app/service.py"
)


def test_language_upsert_matches_live_schema_and_reopen(tmp_path: Path) -> None:
    tree = get_parser("python").parse(FIXTURE.read_bytes())
    assert tree.root_node.named_child_count and not tree.root_node.has_error
    path = tmp_path / "language.db"
    old = LanguageVersion("python", "3.11", features=["old"])
    replacement = LanguageVersion(
        "python",
        "3.11",
        edition="updated",
        build="build-2",
        features=["match", "annotations"],
        release_date=datetime(2022, 10, 24),
        end_of_life=datetime(2027, 10, 1),
    )
    other = LanguageVersion("javascript", "1.0", features=["modules"])
    grammar = GrammarVersion("python", "1.0", "python.so")
    rule = CompatibilityRule(
        "python", ">=3.10", ">=1.0", CompatibilityLevel.FULLY_COMPATIBLE
    )
    change = BreakingChange(
        "python", "3.10", "3.11", "syntax", "Match statement", "medium"
    )
    with CompatibilityDatabase(path) as db:
        assert db.add_language_version(old)
        assert db.add_language_version(other)
        assert db.add_grammar_version(grammar)
        assert db.add_compatibility_rule(rule)
        assert db.add_breaking_change(change)
        assert db.add_language_version(replacement)
        assert db.get_language_versions("python") == [replacement]
        assert db.schema.get_language_versions("python") == [replacement]
        assert db.schema.get_language_versions("javascript") == [other]
        assert db.find_compatible_grammar(replacement) == grammar
        assert db.schema.compatibility_rules == [rule]
        assert db.schema.breaking_changes == [change]
    with CompatibilityDatabase(path) as reopened:
        assert reopened.schema.get_language_versions("python") == [replacement]
        assert reopened.get_language_versions("javascript") == [other]
        assert reopened.find_compatible_grammar(replacement) == grammar
        assert reopened.schema.compatibility_rules == [rule]
        assert reopened.schema.breaking_changes == [change]


def test_grammar_upsert_preserves_metadata_and_persisted_tie_order(
    tmp_path: Path,
) -> None:
    tree = get_parser("python").parse(FIXTURE.read_bytes())
    assert tree.root_node.named_child_count and not tree.root_node.has_error
    path = tmp_path / "grammar.db"
    language = LanguageVersion("python", "3.11", features=["match"])
    first = GrammarVersion("python", "2.0", "first.so")
    second = GrammarVersion("python", "1.0", "second.so")
    other = GrammarVersion("javascript", "1.0", "javascript.so")
    replacement = GrammarVersion(
        "python",
        "2.0",
        "updated.so",
        supported_features=["match", "annotations"],
        min_language_version="3.10",
        max_language_version="3.12",
        breaking_changes=["changed-query"],
        release_date=datetime(2026, 1, 2),
    )
    rule = CompatibilityRule(
        "python", ">=3.10", ">=1.0", CompatibilityLevel.FULLY_COMPATIBLE
    )
    change = BreakingChange(
        "python", "3.10", "3.11", "syntax", "Match statement", "medium"
    )
    with CompatibilityDatabase(path) as db:
        assert db.add_language_version(language)
        assert db.add_grammar_version(first)
        assert db.add_grammar_version(second)
        assert db.add_grammar_version(other)
        assert db.add_compatibility_rule(rule)
        assert db.add_breaking_change(change)
        assert db.find_compatible_grammar(language) == first
        assert db.add_grammar_version(replacement)
        assert db.get_grammar_versions("python") == [second, replacement]
        assert db.schema.get_grammar_versions("python") == [second, replacement]
        assert db.find_compatible_grammar(language) == second
        assert db.schema.get_language_versions("python") == [language]
        assert db.schema.get_grammar_versions("javascript") == [other]
        assert db.schema.compatibility_rules == [rule]
        assert db.schema.breaking_changes == [change]
    with CompatibilityDatabase(path) as reopened:
        assert reopened.schema.get_grammar_versions("python") == [second, replacement]
        assert reopened.find_compatible_grammar(language) == second
        assert reopened.schema.get_grammar_versions("javascript") == [other]
        assert reopened.schema.compatibility_rules == [rule]
        assert reopened.schema.breaking_changes == [change]


@pytest.mark.parametrize("kind", ["language", "grammar"])
@pytest.mark.parametrize("failure", ["statement", "decode", "commit"])
def test_failed_upsert_preserves_live_and_persisted_state(
    tmp_path: Path, kind: str, failure: str
) -> None:
    tree = get_parser("python").parse(FIXTURE.read_bytes())
    assert tree.root_node.named_child_count and not tree.root_node.has_error
    path = tmp_path / f"failed-{kind}.db"
    language = LanguageVersion("python", "3.11", features=["match"])
    grammar = GrammarVersion("python", "1.0", "python.so")
    with CompatibilityDatabase(path) as db:
        db.conn.execute("PRAGMA foreign_keys = ON")
        assert db.add_language_version(language)
        assert db.add_grammar_version(grammar)
        if failure == "statement":
            db.conn.execute(
                f"CREATE TRIGGER reject_replacement BEFORE INSERT ON {kind}_versions "
                "BEGIN SELECT RAISE(ABORT, 'test rejects replacement'); END"
            )
        elif failure == "decode":
            column = "features" if kind == "language" else "supported_features"
            db.conn.execute(
                f"CREATE TRIGGER corrupt_candidate AFTER INSERT ON {kind}_versions "
                f"BEGIN UPDATE {kind}_versions SET {column} = '{{invalid' "
                "WHERE language = NEW.language AND version = NEW.version; END"
            )
        else:
            db.conn.execute("CREATE TABLE commit_parent (id INTEGER PRIMARY KEY)")
            db.conn.execute(
                "CREATE TABLE commit_guard (parent_id INTEGER REFERENCES "
                "commit_parent(id) DEFERRABLE INITIALLY DEFERRED)"
            )
            db.conn.execute(
                f"CREATE TRIGGER reject_commit AFTER INSERT ON {kind}_versions "
                "BEGIN INSERT INTO commit_guard VALUES (1); END"
            )
        db.conn.commit()
        if kind == "language":
            assert not db.add_language_version(
                LanguageVersion("python", "3.11", features=["wrong"])
            )
        else:
            assert not db.add_grammar_version(
                GrammarVersion("python", "1.0", "wrong.so")
            )
        assert db.get_language_versions("python") == [language]
        assert db.get_grammar_versions("python") == [grammar]
        assert db.schema.get_language_versions("python") == [language]
        assert db.schema.get_grammar_versions("python") == [grammar]
        assert db.find_compatible_grammar(language) == grammar
    with CompatibilityDatabase(path) as reopened:
        assert reopened.schema.get_language_versions("python") == [language]
        assert reopened.schema.get_grammar_versions("python") == [grammar]
        assert reopened.find_compatible_grammar(language) == grammar
