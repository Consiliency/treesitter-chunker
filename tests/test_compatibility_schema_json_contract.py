"""Compatibility schema records retain their meaning across JSON storage."""

import json
from pathlib import Path

from chunker import get_parser
from chunker.languages.compatibility.schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    GrammarVersion,
    LanguageVersion,
)


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_schema_json_round_trip_preserves_rules_and_reports_orphans(
    tmp_path: Path,
) -> None:
    source = FIXTURE.read_bytes()
    assert not get_parser("python").parse(source).root_node.has_error

    language = LanguageVersion("python", "3.11", features=["match"])
    grammar = GrammarVersion("python", "1.0", "python.so", supported_features=["match"])
    rule = CompatibilityRule(
        "python", ">=3.10", "1.0", CompatibilityLevel.PARTIALLY_COMPATIBLE
    )
    breaking = BreakingChange(
        "python", "3.10", "3.11", "syntax", "Changed pattern syntax", "medium"
    )
    schema = CompatibilitySchema()
    schema.add_language_version(language)
    schema.add_grammar_version(grammar)
    schema.add_compatibility_rule(rule)
    schema.add_breaking_change(breaking)
    assert schema.validate_schema() == []

    stored = tmp_path / "compatibility.json"
    stored.write_text(json.dumps(schema.to_dict()), encoding="utf-8")
    restored = CompatibilitySchema()
    restored.from_dict(json.loads(stored.read_text(encoding="utf-8")))

    assert restored.validate_schema() == []
    assert restored.get_language_versions("python") == [language]
    assert restored.get_grammar_versions("python") == [grammar]
    assert restored.find_compatible_grammar(language) == grammar
    assert restored.get_compatibility_level(language, grammar) == (
        CompatibilityLevel.PARTIALLY_COMPATIBLE
    )
    assert restored.get_breaking_changes("python", "3.10", "3.11") == [breaking]
    assert restored.to_dict() == schema.to_dict()

    restored.add_compatibility_rule(
        CompatibilityRule(
            "python", ">=3.20", "2.0", CompatibilityLevel.FULLY_COMPATIBLE
        )
    )
    errors = restored.validate_schema()
    assert len(errors) == 2
    assert any("unknown language version" in error for error in errors)
    assert any("unknown grammar version" in error for error in errors)
