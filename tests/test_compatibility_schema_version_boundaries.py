"""Compatibility version boundaries follow parsed source languages."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.compatibility.database import CompatibilityDatabase
from chunker.languages.compatibility.schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    GrammarVersion,
    LanguageVersion,
)


FIXTURES = Path(__file__).parent / "fixtures/boundary_ir/repos"


def test_language_versions_and_rules_respect_inclusive_boundaries() -> None:
    for language, fixture in (
        ("python", FIXTURES / "python/app/service.py"),
        ("javascript", FIXTURES / "javascript/service.js"),
    ):
        assert not get_parser(language).parse(fixture.read_bytes()).root_node.has_error

    assert LanguageVersion("python", "3.11a1").get_major_minor() == (3, 11)
    assert LanguageVersion("python", "3").get_major_minor() == (3, 0)
    current = LanguageVersion("python", "3.11")
    assert current.is_compatible_with(LanguageVersion("python", "3.10"))
    assert current.is_compatible_with(LanguageVersion("python", "3.11"))
    assert not current.is_compatible_with(LanguageVersion("python", "3.12"))
    assert not current.is_compatible_with(LanguageVersion("python", "4.0"))
    assert not current.is_compatible_with(LanguageVersion("javascript", "3.11"))

    rule = CompatibilityRule(
        "python", "3.10-3.12", "1.*", CompatibilityLevel.FULLY_COMPATIBLE
    )
    for version in ("3.10", "3.11", "3.12"):
        assert rule.matches_language_version(LanguageVersion("python", version))
    for version in ("3.9", "3.13"):
        assert not rule.matches_language_version(LanguageVersion("python", version))
    assert not rule.matches_language_version(LanguageVersion("javascript", "3.11"))
    assert rule.matches_grammar_version(GrammarVersion("python", "1.0", "python.so"))
    assert rule.matches_grammar_version(GrammarVersion("python", "1.2", "python.so"))
    assert not rule.matches_grammar_version(
        GrammarVersion("python", "2.0", "python.so")
    )


def test_breaking_change_lookup_includes_endpoints() -> None:
    fixture = FIXTURES / "python/app/service.py"
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error

    change = BreakingChange(
        "python", "3.10", "3.11", "syntax", "Changed pattern syntax", "medium"
    )
    schema = CompatibilitySchema()
    schema.add_breaking_change(change)

    assert schema.get_breaking_changes("python", "3.10", "3.10") == [change]
    assert schema.get_breaking_changes("python", "3.11", "3.11") == [change]
    assert schema.get_breaking_changes("python", "3.12", "3.13") == []
    assert schema.get_breaking_changes("javascript", "3.10", "3.11") == []


def test_breaking_change_lookup_uses_numeric_interval_overlap(tmp_path: Path) -> None:
    fixture = FIXTURES / "python/app/service.py"
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error

    enclosing = BreakingChange(
        "python", "3.9", "3.13", "syntax", "Spanning change", "medium"
    )
    internal = BreakingChange(
        "python", "3.10", "3.10", "syntax", "Internal change", "medium"
    )
    later = BreakingChange("python", "4.0", "4.1", "syntax", "Later change", "medium")
    schema = CompatibilitySchema()
    schema.add_breaking_change(enclosing)
    schema.add_breaking_change(internal)
    schema.add_breaking_change(later)
    assert schema.get_breaking_changes("python", "3.10", "3.11") == [
        enclosing,
        internal,
    ]
    assert schema.get_breaking_changes("python", "3.13", "3.13") == [enclosing]
    assert schema.get_breaking_changes("python", "3.9", "3.11") == [
        enclosing,
        internal,
    ]
    assert schema.get_breaking_changes("python", "3.14", "3.15") == []

    with CompatibilityDatabase(tmp_path / "compatibility.db") as database:
        assert database.add_breaking_change(enclosing)
        assert database.add_breaking_change(internal)
        assert database.add_breaking_change(later)

    with CompatibilityDatabase(tmp_path / "compatibility.db") as reopened:
        assert {
            change.description
            for change in reopened.get_breaking_changes("python", "3.10", "3.11")
        } == {"Spanning change", "Internal change"}
        assert {
            change.description
            for change in reopened.get_breaking_changes("python", "3.9", "3.11")
        } == {"Spanning change", "Internal change"}
        assert reopened.get_breaking_changes("python", "3.14", "3.15") == []
