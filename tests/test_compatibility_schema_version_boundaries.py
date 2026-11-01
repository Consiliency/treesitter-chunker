"""Compatibility version boundaries follow parsed source languages."""

from pathlib import Path

from chunker import get_parser
from chunker.languages.compatibility.database import (
    CompatibilityDatabase,
    DatabaseManager,
)
from chunker.languages.compatibility.schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    GrammarVersion,
    LanguageVersion,
)


FIXTURES = Path(__file__).parent / "fixtures/boundary_ir/repos"


def test_unknown_grammar_versions_do_not_satisfy_numeric_rules() -> None:
    for language, fixture in (
        ("python", FIXTURES / "python/app/service.py"),
        ("javascript", FIXTURES / "javascript/service.js"),
    ):
        tree = get_parser(language).parse(fixture.read_bytes())
        assert not tree.root_node.has_error
        assert tree.root_node.named_child_count > 0
        unknown = GrammarVersion(language, "unknown", f"{language}.so")
        known = GrammarVersion(language, "1.5", f"{language}.so")
        for constraint in (">=1.0", "<=2.0", "1.0-2.0"):
            rule = CompatibilityRule(
                language, "*", constraint, CompatibilityLevel.FULLY_COMPATIBLE
            )
            assert not rule.matches_grammar_version(unknown)
            assert rule.matches_grammar_version(known)
        for constraint in ("*", "unknown"):
            rule = CompatibilityRule(
                language, "*", constraint, CompatibilityLevel.FULLY_COMPATIBLE
            )
            assert rule.matches_grammar_version(unknown)


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
    assert schema.get_breaking_changes("python", "3.11", "3.10") == []

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
        assert reopened.get_breaking_changes("python", "3.11", "3.10") == []


def test_seeded_javascript_edition_change_survives_report_reload(
    tmp_path: Path,
) -> None:
    fixture = FIXTURES / "javascript/service.js"
    assert not get_parser("javascript").parse(fixture.read_bytes()).root_node.has_error

    db_path = tmp_path / "compatibility.db"
    manager = DatabaseManager(db_path)
    manager.add_known_compatibility_data()
    manager.update_breaking_changes()
    manager.database.close()

    reopened = DatabaseManager(db_path)
    try:
        assert (
            len(
                reopened.database.get_breaking_changes("javascript", "ES2015", "ES2015")
            )
            == 1
        )
        assert (
            len(
                reopened.database.schema.get_breaking_changes(
                    "javascript", "ES2015", "ES2023"
                )
            )
            == 1
        )
        assert (
            reopened.database.get_breaking_changes("javascript", "ES2023", "ES2015")
            == []
        )
        assert "Breaking Changes (1):" in reopened.generate_compatibility_report(
            "javascript"
        )
    finally:
        reopened.database.close()


def test_seeded_python_report_uses_numeric_version_bounds(tmp_path: Path) -> None:
    fixture = FIXTURES / "python/app/service.py"
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error

    db_path = tmp_path / "compatibility.db"
    manager = DatabaseManager(db_path)
    manager.add_known_compatibility_data()
    assert manager.database.add_breaking_change(
        BreakingChange("python", "3.11", "3.12", "syntax", "New syntax", "medium")
    )
    manager.database.close()

    reopened = DatabaseManager(db_path)
    try:
        assert "3.11 -> 3.12: New syntax" in reopened.generate_compatibility_report(
            "python"
        )
    finally:
        reopened.database.close()


def test_python_report_bounds_match_prerelease_range_order(tmp_path: Path) -> None:
    fixture = FIXTURES / "python/app/service.py"
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error

    db_path = tmp_path / "compatibility.db"
    with CompatibilityDatabase(db_path) as database:
        assert database.add_language_version(LanguageVersion("python", "3.11a2"))
        assert database.add_language_version(LanguageVersion("python", "3.11.1"))
        assert database.add_breaking_change(
            BreakingChange(
                "python", "3.11.1", "3.11.1", "syntax", "Patch change", "medium"
            )
        )

    manager = DatabaseManager(db_path)
    try:
        assert (
            len(manager.database.get_breaking_changes("python", "3.11a2", "3.11.1"))
            == 1
        )
        assert (
            "3.11.1 -> 3.11.1: Patch change"
            in manager.generate_compatibility_report("python")
        )
    finally:
        manager.database.close()


def _javascript_fixture_parses() -> None:
    fixture = FIXTURES / "javascript/service.js"
    tree = get_parser("javascript").parse(fixture.read_bytes())
    assert not tree.root_node.has_error
    assert tree.root_node.named_child_count > 0


def test_es_versions_respect_grammar_min_max_bounds() -> None:
    """ES editions compare in release order (treesitter-chunker#170)."""
    _javascript_fixture_parses()
    grammar = GrammarVersion(
        "javascript",
        "1.0",
        "javascript.so",
        min_language_version="ES2020",
        max_language_version="ES2023",
    )
    for version in ("ES2020", "ES2021", "ES2023", "es2022"):
        lang = LanguageVersion("javascript", version)
        assert grammar.supports_language_version(lang), version
        assert (
            grammar.get_compatibility_level(lang) == CompatibilityLevel.FULLY_COMPATIBLE
        )
    for version in ("ES3", "ES5", "ES2015", "ES2019", "ES2024", "ES2030"):
        lang = LanguageVersion("javascript", version)
        assert not grammar.supports_language_version(lang), version
        assert grammar.get_compatibility_level(lang) == CompatibilityLevel.INCOMPATIBLE

    legacy = GrammarVersion(
        "javascript",
        "0.9",
        "javascript.so",
        min_language_version="ES3",
        max_language_version="ES5",
    )
    assert legacy.supports_language_version(LanguageVersion("javascript", "ES3"))
    assert legacy.supports_language_version(LanguageVersion("javascript", "ES5"))
    assert not legacy.supports_language_version(LanguageVersion("javascript", "ES2015"))

    assert grammar._compare_versions("ES5", "ES2015") == -1
    assert grammar._compare_versions("ES2023", "ES2020") == 1
    assert grammar._compare_versions("es2020", "ES2020") == 0


def test_uncomparable_versions_are_rejected_not_silently_accepted() -> None:
    _javascript_fixture_parses()
    grammar = GrammarVersion(
        "javascript",
        "1.0",
        "javascript.so",
        min_language_version="ES2020",
        max_language_version="ES2023",
    )
    for version in ("ESNext", "ES6", "ES4", "ES5.1", "ES2014", "1.5", "next"):
        lang = LanguageVersion("javascript", version)
        assert not grammar.supports_language_version(lang), version
        assert grammar.get_compatibility_level(lang) == CompatibilityLevel.INCOMPATIBLE
    for left, right in (("ESNext", "ES2020"), ("ES2020", "1.5"), ("x", "1.0")):
        try:
            grammar._compare_versions(left, right)
        except ValueError:
            pass
        else:  # pragma: no cover - a failed comparison must not be "equal"
            raise AssertionError(f"{left!r} vs {right!r} compared")

    # An uncomparable bound rejects instead of admitting every version.
    open_bound = GrammarVersion(
        "javascript", "1.0", "javascript.so", min_language_version="ESNext"
    )
    assert not open_bound.supports_language_version(
        LanguageVersion("javascript", "ES2023")
    )


def test_es_grammar_selection_excludes_out_of_range_editions() -> None:
    _javascript_fixture_parses()
    schema = CompatibilitySchema()
    modern = GrammarVersion(
        "javascript",
        "2.0",
        "javascript-modern.so",
        min_language_version="ES2020",
        max_language_version="ES2023",
    )
    classic = GrammarVersion(
        "javascript",
        "1.0",
        "javascript-classic.so",
        min_language_version="ES2015",
        max_language_version="ES2019",
    )
    schema.add_grammar_version(modern)
    schema.add_grammar_version(classic)

    def select(version: str) -> GrammarVersion | None:
        return schema.find_compatible_grammar(LanguageVersion("javascript", version))

    assert select("ES2015") is classic
    assert select("ES2019") is classic
    assert select("ES2020") is modern
    assert select("ES2023") is modern
    assert select("ES2030") is None
    assert select("ES5") is None
    assert select("ESNext") is None


def test_numeric_bounds_are_unchanged_by_es_ordering() -> None:
    fixture = FIXTURES / "python/app/service.py"
    assert not get_parser("python").parse(fixture.read_bytes()).root_node.has_error
    grammar = GrammarVersion(
        "python",
        "1.0",
        "python.so",
        min_language_version="3.8",
        max_language_version="3.12",
    )
    for version in ("3.8", "3.10", "3.12", "3.11a1", "3.8.1"):
        assert grammar.supports_language_version(LanguageVersion("python", version))
    for version in ("3.7", "3.13", "4.0", "ES2020"):
        assert not grammar.supports_language_version(LanguageVersion("python", version))
