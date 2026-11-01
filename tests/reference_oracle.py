"""Load and resolve the shared reference fixture oracles (IF-0-REFS-1).

Each fixture under ``tests/fixtures/references/<language>/`` has a sibling
``<stem>.oracle.json`` that follows ``oracle.schema.json``. An oracle names
scopes by anchor (node type plus tree-sitter start point) and records, per
issue, expected definitions, binding targets, expression uses, visible names,
evaluation scopes and dependency-context summaries. Language test modules
consume the oracle through :func:`load_reference_case`; they parse the fixture
with the real pinned parser and never mock native nodes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator
from chunker.parser import get_parser

if TYPE_CHECKING:
    from tree_sitter import Node

REFERENCES_ROOT = Path(__file__).parent / "fixtures" / "references"
SCHEMA_PATH = REFERENCES_ROOT / "oracle.schema.json"
SCHEMA_ID = "treesitter-chunker.reference-oracle.v1"
LANGUAGES = ("python", "javascript")


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def oracle_paths(language: str | None = None) -> list[Path]:
    """Return every checked-in oracle, optionally for one language."""
    languages = (language,) if language else LANGUAGES
    return sorted(
        path
        for name in languages
        for path in (REFERENCES_ROOT / name).glob("*.oracle.json")
    )


def find_anchor(root: Node, node_type: str, row: int, column: int) -> Node:
    """Return the single named node of ``node_type`` starting at the point."""
    matches = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node.start_point.row > row:
            continue
        if node.end_point.row < row:
            continue
        if (
            node.is_named
            and node.type == node_type
            and tuple(node.start_point) == (row, column)
        ):
            matches.append(node)
        pending.extend(node.children)
    if len(matches) != 1:
        msg = f"{len(matches)} {node_type!r} nodes start at {row}:{column}"
        raise LookupError(msg)
    return matches[0]


@dataclass(frozen=True)
class ReferenceCase:
    """A parsed fixture together with its validated oracle."""

    oracle_path: Path
    oracle: dict[str, Any]
    source: bytes
    root: Node

    @property
    def language(self) -> str:
        return self.oracle["language"]

    def scope(self, scope_id: str) -> Node:
        """Return the node that the oracle's scope id names."""
        anchor = self.oracle["scopes"][scope_id]
        return find_anchor(
            self.root, anchor["node_type"], anchor["row"], anchor["column"]
        )

    def node(self, entry: dict[str, Any]) -> Node:
        """Return the node that a definition, enclosing or context entry names."""
        return find_anchor(self.root, entry["node_type"], entry["row"], entry["column"])

    def occurrence(self, entry: dict[str, Any]) -> Node:
        """Return the leaf node of an occurrence and check its text."""
        node = find_anchor(
            self.root,
            entry.get("node_type", "identifier"),
            entry["row"],
            entry["column"],
        )
        text = node.text.decode("utf-8") if node.text else ""
        if text != entry["name"]:
            msg = f"occurrence text {text!r} is not {entry['name']!r}"
            raise LookupError(msg)
        return node

    def entries(self, section: str, issue: str) -> list[dict[str, Any]]:
        """Return one section's expectations for one issue."""
        return [
            entry for entry in self.oracle.get(section, []) if entry["issue"] == issue
        ]


def validate_oracle(oracle: dict[str, Any]) -> list[str]:
    """Return schema violations for an oracle document."""
    errors = [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in _validator().iter_errors(oracle)
    ]
    if oracle.get("schema") != SCHEMA_ID:
        errors.append(f"schema must be {SCHEMA_ID!r}")
    return errors


def load_reference_case(oracle_path: Path) -> ReferenceCase:
    """Validate an oracle and parse its fixture with the real parser."""
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    errors = validate_oracle(oracle)
    if errors:
        raise ValueError(f"{oracle_path}: " + "; ".join(errors))
    if oracle_path.parent.name != oracle["language"]:
        msg = f"{oracle_path}: oracle lives outside its language directory"
        raise ValueError(msg)
    fixture = oracle_path.with_name(oracle["fixture"])
    expected_name = oracle_path.name.removesuffix(".oracle.json")
    if fixture.stem != expected_name:
        msg = f"{oracle_path}: fixture {fixture.name} does not match oracle name"
        raise ValueError(msg)
    source = fixture.read_bytes()
    root = get_parser(oracle["language"]).parse(source).root_node
    return ReferenceCase(oracle_path, oracle, source, root)


def reference_case(language: str, stem: str) -> ReferenceCase:
    """Load the named fixture's oracle for a language."""
    return load_reference_case(REFERENCES_ROOT / language / f"{stem}.oracle.json")
