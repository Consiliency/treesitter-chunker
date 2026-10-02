"""Persisted compatibility records keep their selection behavior after reopen."""

from pathlib import Path

from chunker.languages.compatibility.database import CompatibilityDatabase
from chunker.languages.compatibility.schema import (
    CompatibilityLevel,
    CompatibilityRule,
    GrammarVersion,
    LanguageVersion,
)


def test_reopened_database_uses_persisted_grammar_and_rule(tmp_path: Path) -> None:
    db_path = tmp_path / "compatibility.db"
    language = LanguageVersion("python", "3.11", features=["match"])
    grammar = GrammarVersion("python", "1.0", "python.so", max_language_version="3.10")
    other_language = LanguageVersion("javascript", "3.11")
    other_grammar = GrammarVersion("javascript", "1.0", "javascript.so")
    rule = CompatibilityRule(
        "python", ">=3.10", ">=1.0", CompatibilityLevel.FULLY_COMPATIBLE
    )

    with CompatibilityDatabase(db_path) as db:
        assert db.add_language_version(language)
        assert db.add_grammar_version(grammar)
        assert db.add_language_version(other_language)
        assert db.add_grammar_version(other_grammar)
        assert db.add_compatibility_rule(rule)
        assert db.find_compatible_grammar(language) == grammar

    with CompatibilityDatabase(db_path) as reopened:
        assert reopened.get_language_versions("python") == [language]
        assert reopened.get_grammar_versions("python") == [grammar]
        assert reopened.get_language_versions("javascript") == [other_language]
        assert reopened.find_compatible_grammar(language) == grammar
        assert reopened.get_compatibility_level(language, grammar) == (
            CompatibilityLevel.FULLY_COMPATIBLE
        )
        export_path = tmp_path / "compatibility.json"
        backup_path = tmp_path / "compatibility.backup.db"
        reopened.export_database(export_path)
        reopened.backup_database(backup_path)

    with CompatibilityDatabase(tmp_path / "imported.db") as imported:
        imported.import_database(export_path)
        assert imported.find_compatible_grammar(language) == grammar

    with CompatibilityDatabase(tmp_path / "restored.db") as restored:
        restored.restore_database(backup_path)
        assert restored.find_compatible_grammar(language) == grammar
