"""The binding allow-list (treesitter-chunker#682, plan section 7.5).

Node kinds come from the loaded ``Language``, so this runs in CI without
grammar sources. Every named kind of a reviewed grammar must be classified,
so a grammar bump cannot add an unreviewed binding form. At this head the
JavaScript, TypeScript and TSX grammars are reviewed (the JS/TS analyzer);
Python is reviewed with its analyzer.
"""

from __future__ import annotations

import pytest

from chunker.call_resolution import allowlist
from chunker.call_resolution.allowlist import (
    ALLOWLIST,
    FAIL_CLOSED,
    HANDLED,
    IGNORED,
    NON_BINDING,
    PINNED_GRAMMARS,
    REVIEWED_LANGUAGES,
    Entry,
)

# Kinds the plan names explicitly (7.5) and that the pinned grammars have.
KNOWN_KINDS = {
    "python": {"function_definition", "class_definition", "lambda", "global_statement"},
    "javascript": {
        "function_declaration",
        "class_declaration",
        "using_declaration",
        "for_in_statement",
    },
    "typescript": {"function_signature", "import_alias", "internal_module"},
    "tsx": {"function_signature", "import_alias", "jsx_element"},
}


@pytest.mark.parametrize("language", PINNED_GRAMMARS)
def test_node_kinds_enumerate_from_the_loaded_language(language: str) -> None:
    kinds = allowlist.named_node_kinds(language)
    assert len(kinds) > 100
    assert KNOWN_KINDS[language] <= kinds


@pytest.mark.parametrize("language", PINNED_GRAMMARS)
def test_entries_name_real_kinds_with_valid_classifications(language: str) -> None:
    entries = ALLOWLIST[language]
    assert (
        allowlist.unknown_entries(allowlist.named_node_kinds(language), entries) == []
    )
    assert allowlist.invalid_entries(entries) == []


def test_reviewed_grammars_classify_every_named_kind() -> None:
    """Each analyzer change lists its grammars; JS/TS at this head."""
    assert {"javascript", "typescript", "tsx"} <= REVIEWED_LANGUAGES
    for language in sorted(REVIEWED_LANGUAGES):
        kinds = allowlist.named_node_kinds(language)
        assert allowlist.unclassified_kinds(kinds, ALLOWLIST[language]) == [], language


def test_reviewed_languages_are_pinned_grammars() -> None:
    assert set(ALLOWLIST) == set(PINNED_GRAMMARS)
    assert set(PINNED_GRAMMARS) >= REVIEWED_LANGUAGES


def test_an_unclassified_kind_fails_closed() -> None:
    for language in PINNED_GRAMMARS:
        entry = allowlist.classify(language, "a_kind_no_grammar_has")
        assert entry.classification == FAIL_CLOSED
    assert (
        allowlist.classify("go", "function_declaration").classification == FAIL_CLOSED
    )


def test_completeness_check_flags_unclassified_kinds() -> None:
    """Self-test: the reviewed-grammar check fails on a missing kind."""
    kinds = {"function_declaration", "statement_label", "identifier", "new_form"}
    entries = {
        "function_declaration": Entry(HANDLED, "symbol"),
        "statement_label": Entry(IGNORED, "labels bind no value"),
        "identifier": Entry(NON_BINDING),
    }
    assert allowlist.unclassified_kinds(kinds, entries) == ["new_form"]
    entries["new_form"] = Entry(FAIL_CLOSED, "not reviewed")
    assert allowlist.unclassified_kinds(kinds, entries) == []
    assert allowlist.unknown_entries(kinds, {"typo_kind": Entry(NON_BINDING)}) == [
        "typo_kind"
    ]
    assert allowlist.invalid_entries(
        {"a": Entry("maybe"), "b": Entry(HANDLED), "c": Entry(NON_BINDING)}
    ) == ["a", "b"]
