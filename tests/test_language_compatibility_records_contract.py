"""Language constraints and persisted rules keep grammar selection stable."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.compatibility.database import CompatibilityDatabase
from chunker.languages.compatibility.schema import (
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
