"""Persisted compatibility records restore selection after a cold open."""

from pathlib import Path

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
