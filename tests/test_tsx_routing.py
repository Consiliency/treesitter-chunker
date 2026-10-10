""".tsx files are parsed with the tsx grammar and labelled ``tsx``.

The ``typescript`` grammar cannot parse JSX, so a ``.tsx`` file with JSX used
to parse with errors and lose declarations: in the fixture below the class
``Panel`` and its ``render`` method were dropped entirely. Consumers that
re-parse a file with the IR's ``files[].language`` (as spec's coverage check
does) must get the grammar that actually parses it, so the label is ``tsx``.
"""

from chunker import extract_boundary_ir
from chunker.auto import ZeroConfigAPI
from chunker.parser import get_parser

TSX_SOURCE = """import React from "react";

interface CardProps {
  title: string;
  count?: number;
}

export function Card({ title, count = 0 }: CardProps): JSX.Element {
  return (
    <div className="card">
      <h1>{title}</h1>
      <span>{count}</span>
    </div>
  );
}

export const Badge = (props: { label: string }) => <b>{props.label}</b>;

export class Panel extends React.Component<CardProps> {
  render() {
    return <>{this.props.title}</>;
  }
}

type Mode = "a" | "b";
"""


def _ir(tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return extract_boundary_ir(str(tmp_path), canonical=True, include_timings=False)


def test_tsx_extension_routes_to_tsx_grammar():
    assert ZeroConfigAPI.EXTENSION_MAP[".tsx"] == "tsx"
    assert ZeroConfigAPI.EXTENSION_MAP[".ts"] == "typescript"
    assert ZeroConfigAPI.EXTENSION_MAP[".jsx"] == "javascript"


def test_tsx_file_with_jsx_parses_cleanly_and_keeps_declarations(tmp_path):
    ir = _ir(tmp_path, "Card.tsx", TSX_SOURCE)
    (file_record,) = ir["files"]
    # Fault: `.tsx` was labelled and parsed as `typescript`.
    assert file_record["language"] == "tsx"
    tree = get_parser(file_record["language"]).parse(TSX_SOURCE.encode("utf-8"))
    assert tree.root_node.has_error is False


def test_tsx_file_keeps_jsx_returning_declarations(tmp_path):
    ir = _ir(tmp_path, "Card.tsx", TSX_SOURCE)
    nodes = {(node["kind"], node["qualified_name"]): node for node in ir["nodes"]}
    # Fault: the typescript grammar dropped the JSX-returning class entirely.
    assert ("class", "Panel") in nodes
    assert ("method", "Panel.render") in nodes
    assert ("interface", "CardProps") in nodes
    assert ("variable_declarator", "Badge") in nodes
    # TypeScript metadata still applies to tsx trees.
    card = next(
        node
        for node in ir["nodes"]
        if node["kind"] == "function" and node["qualified_name"] == "Card"
    )
    # (Destructured parameters are a separate, pre-existing TypeScript gap.)
    assert card["signature"].startswith("Card(")
    assert card["signature"].endswith(") -> JSX.Element")
    assert card["language"] == "tsx"


def test_ts_file_unchanged(tmp_path):
    source = "export function add(a: number, b: number): number { return a + b; }\n"
    ir = _ir(tmp_path, "math.ts", source)
    (file_record,) = ir["files"]
    assert file_record["language"] == "typescript"
    (add,) = [node for node in ir["nodes"] if node["kind"] == "function"]
    assert add["signature"] == "add(a: number, b: number) -> number"


def test_jsx_file_parses_with_javascript_grammar(tmp_path):
    source = "export function Thing({ name }) {\n  return <div>{name}</div>;\n}\n"
    ir = _ir(tmp_path, "Thing.jsx", source)
    (file_record,) = ir["files"]
    assert file_record["language"] == "javascript"
    tree = get_parser("javascript").parse(source.encode("utf-8"))
    assert tree.root_node.has_error is False
