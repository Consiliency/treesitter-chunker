"""Language constraints and persisted rules keep grammar selection stable."""

import json
from pathlib import Path

from chunker import get_parser
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
    with CompatibilityDatabase(destination_path) as destination:
        assert destination.add_language_version(LanguageVersion("rust", "2021"))
        destination.import_database(export_path)

    with CompatibilityDatabase(destination_path) as reopened:
        assert reopened.get_language_versions("python") == [python]
        assert reopened.get_language_versions("javascript") == [javascript]
        assert reopened.get_language_versions("rust") == []
        assert reopened.get_grammar_versions("python") == [python_grammar]
        assert reopened.get_grammar_versions("javascript") == [javascript_grammar]
        assert reopened.get_compatibility_level(python, python_grammar) == (
            CompatibilityLevel.PARTIALLY_COMPATIBLE
        )
        assert reopened.get_breaking_changes("python", "0.9", "1.0") == [breaking]
