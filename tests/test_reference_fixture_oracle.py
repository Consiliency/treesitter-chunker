"""Integrity of the shared reference fixture suite (IF-0-REFS-1).

These checks keep the oracles truthful about the fixtures they describe. They
do not exercise the reference APIs; the per-language contract tests do that.
"""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING

import pytest
from tests.reference_oracle import (
    REFERENCES_ROOT,
    LANGUAGES,
    ReferenceCase,
    load_reference_case,
    oracle_paths,
    validate_oracle,
)

if TYPE_CHECKING:
    from tree_sitter import Node

REFS_ISSUES = {
    "python": {
        "treesitter-chunker#274",
        "treesitter-chunker#278",
        "treesitter-chunker#294",
    },
    "javascript": {"treesitter-chunker#289", "treesitter-chunker#293"},
}

ORACLES = oracle_paths()


def _contains(outer: Node, inner: Node) -> bool:
    return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte


def _defines(node: Node, name: str) -> bool:
    if node.type == "identifier":
        return node.text == name.encode("utf-8")
    target = node.child_by_field_name("name") or node.child_by_field_name("left")
    return target is not None and target.text == name.encode("utf-8")


def _polarities(case: ReferenceCase) -> dict[str, set[str]]:
    """Map each issue to the expectation polarities its entries carry."""
    seen: dict[str, set[str]] = {}

    def mark(issue: str, *polarities: str) -> None:
        seen.setdefault(issue, set()).update(polarities)

    oracle = case.oracle
    for entry in oracle.get("definitions", []):
        mark(entry["issue"], "positive" if entry["expect"] == "found" else "negative")
    for entry in oracle.get("occurrences", []):
        mark(entry["issue"], "positive" if entry["role"] == "use" else "negative")
    for entry in oracle.get("visible", []):
        if entry["includes"]:
            mark(entry["issue"], "positive")
        if entry["excludes"]:
            mark(entry["issue"], "negative")
    for entry in oracle.get("enclosing", []):
        mark(entry["issue"], "positive", "negative")
    for entry in oracle.get("dependency_context", []):
        mark(entry["issue"], "positive", "negative")
    return seen


def test_suite_layout_covers_every_refs_issue() -> None:
    assert {path.parent.name for path in ORACLES} == set(LANGUAGES)
    for language in LANGUAGES:
        issues = set()
        for path in oracle_paths(language):
            issues.update(json.loads(path.read_text(encoding="utf-8"))["issues"])
        assert issues == REFS_ISSUES[language]
    fixtures = {
        path.name
        for language in LANGUAGES
        for path in (REFERENCES_ROOT / language).iterdir()
        if not path.name.endswith(".oracle.json")
    }
    oracles = {
        json.loads(path.read_text(encoding="utf-8"))["fixture"] for path in ORACLES
    }
    assert fixtures == oracles


@pytest.mark.parametrize("oracle_path", ORACLES, ids=lambda path: path.name)
def test_oracle_anchors_resolve_on_real_parse(oracle_path) -> None:
    case = load_reference_case(oracle_path)
    oracle = case.oracle
    assert not case.root.has_error
    assert case.scope("root") == case.root

    scopes = {scope_id: case.scope(scope_id) for scope_id in oracle["scopes"]}
    declared = set(oracle["issues"])
    sections = ("definitions", "occurrences", "visible", "enclosing")
    for section in (*sections, "dependency_context"):
        for entry in oracle.get(section, []):
            assert entry["issue"] in declared, entry
            assert entry["scope"] in scopes, entry

    for entry in oracle.get("definitions", []):
        if entry["expect"] == "found":
            assert _defines(case.node(entry), entry["name"]), entry
    for entry in oracle.get("occurrences", []):
        assert _contains(scopes[entry["scope"]], case.occurrence(entry)), entry
    for entry in oracle.get("visible", []):
        assert not set(entry["includes"]) & set(entry["excludes"]), entry
    for entry in oracle.get("enclosing", []):
        node = case.node(entry)
        assert entry["not_scope"] in scopes, entry
        assert entry["scope"] != entry["not_scope"], entry
        assert _contains(scopes[entry["scope"]], node), entry
        assert _contains(scopes[entry["not_scope"]], node), entry
    for entry in oracle.get("dependency_context", []):
        assert _defines(case.node(entry), entry["name"]), entry

    polarities = _polarities(case)
    for issue in declared:
        assert polarities.get(issue) == {"positive", "negative"}, issue


@pytest.mark.parametrize("oracle_path", ORACLES, ids=lambda path: path.name)
def test_oracle_occurrences_are_unique(oracle_path) -> None:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    points = [
        (entry["row"], entry["column"]) for entry in oracle.get("occurrences", [])
    ]
    assert len(points) == len(set(points))


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda oracle: oracle.pop("scopes"), "'scopes' is a required property"),
        (
            lambda oracle: oracle["definitions"][0].pop("issue"),
            "is not valid under any of the given schemas",
        ),
        (
            lambda oracle: oracle["definitions"][0].update(issue="#274"),
            "is not valid under any of the given schemas",
        ),
        (
            lambda oracle: oracle["scopes"].pop("root"),
            "'root' is a required property",
        ),
        (
            lambda oracle: oracle["definitions"].append(
                {
                    "issue": "treesitter-chunker#274",
                    "name": "x",
                    "scope": "root",
                    "expect": "absent",
                    "row": 1,
                }
            ),
            "is not valid under any of the given schemas",
        ),
    ],
)
def test_schema_rejects_malformed_oracles(mutate, fragment) -> None:
    path = REFERENCES_ROOT / "python" / "module_definitions.oracle.json"
    oracle = json.loads(path.read_text(encoding="utf-8"))
    assert validate_oracle(oracle) == []
    broken = copy.deepcopy(oracle)
    mutate(broken)
    errors = validate_oracle(broken)
    assert any(fragment in error for error in errors), errors
