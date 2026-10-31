"""JavaScript dependency context and reference lookup against the shared oracles.

Each test consumes one issue's fixture contract from
``tests/fixtures/references/javascript`` (IF-0-REFS-1) and parses it with the
real pinned parser.
"""

from __future__ import annotations

from chunker.context.factory import ContextFactory
from tests.reference_oracle import reference_case

ISSUE_289 = "treesitter-chunker#289"


def test_289_generator_context_keeps_signature_and_omits_body() -> None:
    case = reference_case("javascript", "generator_context")
    assert not case.root.has_error
    mismatches = []
    for entry in case.entries("dependency_context", ISSUE_289):
        item = ContextFactory.create_context_extractor("javascript")._find_definition(
            entry["name"], case.scope(entry["scope"]), case.root, case.source
        )
        if item is None or item.node != case.node(entry):
            mismatches.append((entry["name"], "definition", item))
            continue
        missing = [text for text in entry["includes"] if text not in item.content]
        leaked = [text for text in entry["excludes"] if text in item.content]
        if missing or leaked:
            mismatches.append((entry["name"], item.content, missing, leaked))
    assert mismatches == []


def test_289_consumer_dependencies_summarize_every_generator() -> None:
    case = reference_case("javascript", "generator_context")
    consumer = case.scope("consumer")
    dependencies = ContextFactory.create_context_extractor(
        "javascript"
    ).extract_dependencies(consumer, case.root, case.source)
    by_line = {item.line_number: item.content for item in dependencies}
    expected = {
        entry["row"] + 1: entry
        for entry in case.entries("dependency_context", ISSUE_289)
    }
    assert set(by_line) >= set(expected)
    for line, entry in expected.items():
        content = by_line[line]
        assert all(text in content for text in entry["includes"]), content
        assert not any(text in content for text in entry["excludes"]), content
