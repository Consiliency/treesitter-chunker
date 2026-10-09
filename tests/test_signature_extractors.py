"""Signature metadata for methods and member declarations across languages.

Each case parses real source with the locked grammar and checks the public
chunk metadata (``signature`` and the formatted ``signature_text``) plus, where
noted, the Boundary IR ``signature`` field. The named faults guard specific
regressions:

* Go (treesitter-chunker#352): identifier-only name lookup, the receiver list
  read as arguments, and an omitted or truncated result list.
* Rust (treesitter-chunker#367): an omitted ``&self`` receiver and an omitted
  ``-> return`` type.
"""

from __future__ import annotations

from pathlib import Path


import chunker
from chunker.core import chunk_text


def _signed(code: str, language: str) -> dict[str, dict]:
    """Map signature name -> chunk metadata for every signed chunk."""
    chunks = chunk_text(
        code,
        language,
        extract_metadata=True,
        include_retrieval_metadata=True,
    )
    out: dict[str, dict] = {}
    for chunk in chunks:
        signature = chunk.metadata.get("signature")
        if signature:
            out[signature["name"]] = chunk.metadata
    return out


def _boundary_signatures(tmp_path: Path, filename: str, code: str) -> dict:
    path = tmp_path / filename
    path.write_text(code, encoding="utf-8")
    ir = chunker.extract_boundary_ir(
        str(tmp_path), canonical=True, include_timings=False
    )
    return {
        node["qualified_name"]: node["signature"]
        for node in ir["nodes"]
        if node.get("signature")
    }


# --------------------------------------------------------------------------- #
# Go (treesitter-chunker#352)
# --------------------------------------------------------------------------- #

GO_ISSUE_352 = """package gateway

type Gateway struct{}
func (g *Gateway) Dispatch(id string) (string, error) { return "", nil }
"""


def test_go_method_signature_issue_352_repro():
    signed = _signed(GO_ISSUE_352, "go")
    metadata = signed["Dispatch"]
    signature = metadata["signature"]
    # Fault: identifier-only name lookup returned None for field_identifier.
    assert signature["name"] == "Dispatch"
    # Fault: the receiver list was read as the argument list.
    assert signature["parameters"] == ["id string"]
    assert signature["receiver"] == "g *Gateway"
    assert "method" in signature["modifiers"]
    # Fault: the result list was omitted (or had its parentheses stripped).
    assert signature["return_type"] == "(string, error)"
    assert metadata["signature_text"] == "Dispatch(id string) -> (string, error)"


def test_go_method_value_receiver_single_result():
    code = """package handler

type Handler struct{ Name string }

func (h Handler) Dispatch(toolId string) string {
\treturn toolId
}
"""
    metadata = _signed(code, "go")["Dispatch"]
    assert metadata["signature"]["receiver"] == "h Handler"
    assert metadata["signature_text"] == "Dispatch(toolId string) -> string"


def test_go_function_signature_keeps_result_and_has_no_receiver():
    code = """package handler

func Label(value string) string { return value }
func Pair(a, b int, s ...string) (n int, err error) { return 0, nil }
func Nothing() {}
"""
    signed = _signed(code, "go")
    assert signed["Label"]["signature_text"] == "Label(value string) -> string"
    assert "receiver" not in signed["Label"]["signature"]
    assert signed["Label"]["signature"]["modifiers"] == []
    assert signed["Pair"]["signature"]["parameters"] == ["a, b int", "s ...string"]
    assert signed["Pair"]["signature"]["return_type"] == "(n int, err error)"
    assert signed["Nothing"]["signature_text"] == "Nothing()"


def test_go_method_signature_in_boundary_ir(tmp_path):
    signatures = _boundary_signatures(tmp_path, "gateway.go", GO_ISSUE_352)
    assert signatures["Dispatch"] == "Dispatch(id string) -> (string, error)"


# --------------------------------------------------------------------------- #
# Rust (treesitter-chunker#367)
# --------------------------------------------------------------------------- #

RUST_ISSUE_367 = """struct Gateway;

impl Gateway {
    pub fn dispatch(&self, id: &str) -> String { String::new() }
}
"""


def test_rust_impl_method_issue_367_repro():
    metadata = _signed(RUST_ISSUE_367, "rust")["dispatch"]
    signature = metadata["signature"]
    # Fault: the receiver is omitted from the parameter list.
    assert signature["parameters"] == ["&self", "id: &str"]
    assert signature["receiver"] == "&self"
    # Fault: the return type is omitted.
    assert signature["return_type"] == "String"
    assert signature["modifiers"] == ["pub"]
    assert metadata["signature_text"] == "dispatch(&self, id: &str) -> String"


def test_rust_receiver_forms_and_free_functions():
    code = """struct S;

impl S {
    fn len(&self) -> usize { 0 }
    fn push(&mut self, v: u32) {}
    fn take(self) -> Result<(), std::io::Error> { Ok(()) }
    fn new() -> Self { S }
}

pub fn label(value: &str) -> String { value.to_string() }
"""
    signed = _signed(code, "rust")
    assert signed["len"]["signature_text"] == "len(&self) -> usize"
    assert signed["push"]["signature"]["receiver"] == "&mut self"
    assert signed["push"]["signature_text"] == "push(&mut self, v: u32)"
    assert signed["take"]["signature"]["return_type"] == "Result<(), std::io::Error>"
    assert signed["take"]["signature"]["receiver"] == "self"
    assert signed["new"]["signature_text"] == "new() -> Self"
    assert "receiver" not in signed["new"]["signature"]
    assert signed["label"]["signature_text"] == "label(value: &str) -> String"
    assert "receiver" not in signed["label"]["signature"]
