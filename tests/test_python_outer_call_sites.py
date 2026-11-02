"""Outer Python call sites for callable-return expressions (treesitter-chunker#516).

Real-parser fixtures; no fixture source is executed. Expected callee and call
spans come from searching the raw bytes, and lines from counting LF, never
from the producer's spans.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chunker import chunk_file, get_parser, symbol_graph

MODES = ("permissive", "strict")


def calls(graph):
    return [r for r in graph["relationships"] if r["type"] == "calls"]


def write(tmp_path: Path, text: str) -> tuple[Path, bytes]:
    path = tmp_path / "audit.py"
    path.write_bytes(text.encode("utf-8"))
    raw = path.read_bytes()
    assert not get_parser("python").parse(raw).root_node.has_error
    return path, raw


def owner_id(path: Path, name: str) -> str:
    facts = symbol_graph.extract_symbol_facts_for_file(
        path, path, "python", fail_fast=True
    )
    return next(
        key for key, row in facts["symbol_lookup"].items() if row["name"] == name
    )


def expected_site(raw: bytes, callee: str, start: int) -> dict:
    """Oracle for one call site whose callee text starts at ``start``."""
    callee_bytes = callee.encode("utf-8")
    assert raw[start : start + len(callee_bytes)] == callee_bytes
    callee_end = start + len(callee_bytes)
    # The fixtures call with an empty or single-token argument list right
    # after the callee: find its closing parenthesis.
    assert raw[callee_end : callee_end + 1] == b"("
    call_end = raw.index(b")", callee_end) + 1
    line = raw[:start].count(b"\n") + 1
    return {
        "reference": callee,
        "callee_byte_start": start,
        "callee_byte_end": callee_end,
        "byte_start": start,
        "byte_end": call_end,
        "line": line,
        "end_line": raw[: call_end - 1].count(b"\n") + 1,
    }


def observed(row: dict) -> dict:
    return {
        "reference": row["reference"],
        "callee_byte_start": row["callee_byte_start"],
        "callee_byte_end": row["callee_byte_end"],
        "byte_start": row["location"]["byte_start"],
        "byte_end": row["location"]["byte_end"],
        "line": row["line"],
        "end_line": row["location"]["end_line"],
    }


def assert_unresolved(row: dict, raw: bytes) -> None:
    assert row["resolution"] == "unresolved"
    assert row["candidates"] == []
    assert row["is_internal"] is False
    assert row["to"] == row["reference"]
    callee = raw[row["callee_byte_start"] : row["callee_byte_end"]]
    assert callee.decode("utf-8") == row["reference"]


@pytest.mark.parametrize("mode", MODES)
def test_getattr_outer_site_is_emitted_beside_inner_site(tmp_path, mode):
    path, raw = write(
        tmp_path,
        "def audit():\n    return 1\n\n"
        "def caller(obj):\n    return getattr(obj, 'audit')()\n",
    )
    graph = symbol_graph.extract_symbol_graph(
        path, "python", resolution_mode=mode, fail_fast=True
    )
    start = raw.index(b"getattr")
    inner = expected_site(raw, "getattr", start)
    outer = expected_site(raw, "getattr(obj, 'audit')", start)
    rows = calls(graph)
    assert [observed(row) for row in rows] == [inner, outer]
    caller = owner_id(path, "caller")
    audit = owner_id(path, "audit")
    for row in rows:
        assert row["from"] == caller
        assert row["file"] == "audit.py"
        assert row["call_kind"] == "call"
        assert row["call_site_id"].startswith("call:")
        assert_unresolved(row, raw)
        # The dynamic call never binds the local ``audit`` definition.
        assert audit not in (row["to"], *row["candidates"])
    assert len({row["call_site_id"] for row in rows}) == 2
    assert len(graph["call_facts"]) == 2
    assert graph == symbol_graph.extract_symbol_graph(
        path, "python", resolution_mode=mode, fail_fast=True
    )


def test_chained_self_qualified_and_repeated_outer_sites(tmp_path):
    path, raw = write(
        tmp_path,
        "class Box:\n"
        "    def factory(self):\n        return len\n\n"
        "    def run(self, mod, y):\n"
        "        f()()()\n"
        "        self.factory()(y)\n"
        "        mod.make(y)(y)\n"
        "        getattr(mod, 'x')()\n"
        "        getattr(mod, 'x')()\n",
    )
    rows = calls(symbol_graph.extract_symbol_graph(path, "python", fail_fast=True))
    expected = []
    chain = raw.index(b"f()()()")
    for callee in ("f", "f()", "f()()"):
        expected.append(expected_site(raw, callee, chain))
    factory = raw.index(b"self.factory")
    expected.append(expected_site(raw, "self.factory", factory))
    expected.append(expected_site(raw, "self.factory()", factory))
    make = raw.index(b"mod.make")
    expected.append(expected_site(raw, "mod.make", make))
    expected.append(expected_site(raw, "mod.make(y)", make))
    first = raw.index(b"getattr")
    second = raw.index(b"getattr", first + 1)
    for start in (first, second):
        expected.append(expected_site(raw, "getattr", start))
        expected.append(expected_site(raw, "getattr(mod, 'x')", start))

    def order(site):
        return tuple(site.values())

    assert sorted(map(observed, rows), key=order) == sorted(expected, key=order)
    run = owner_id(path, "run")
    assert {row["from"] for row in rows} == {run}
    # Repeated identical text at another span is a distinct site.
    assert len({row["call_site_id"] for row in rows}) == len(rows) == len(expected)
    for row in rows:
        if row["reference"] not in {"f", "self.factory", "mod.make", "getattr"}:
            assert_unresolved(row, raw)


def test_commented_inner_call_cannot_bind_local_definition(tmp_path):
    reference = "getattr(obj,  # audit\n        'audit')"
    path, raw = write(
        tmp_path,
        "def audit():\n    return 1\n\n"
        "def caller(obj):\n    return " + reference + "()\n",
    )
    for mode in MODES:
        rows = calls(
            symbol_graph.extract_symbol_graph(
                path, "python", resolution_mode=mode, fail_fast=True
            )
        )
        outer = [row for row in rows if row["reference"] == reference]
        assert len(outer) == 1
        assert observed(outer[0]) == expected_site(
            raw, reference, raw.index(b"getattr")
        )
        assert_unresolved(outer[0], raw)
        assert outer[0]["from"] == owner_id(path, "caller")
        assert [row["reference"] for row in rows] == ["getattr", reference]


def test_decorator_outer_call_site(tmp_path):
    path, raw = write(
        tmp_path,
        "def make():\n    return lambda f: f\n\n"
        "@make()()\ndef target():\n    return 1\n",
    )
    rows = calls(symbol_graph.extract_symbol_graph(path, "python", fail_fast=True))
    start = raw.index(b"make()()")
    assert [observed(row) for row in rows] == [
        expected_site(raw, "make", start),
        expected_site(raw, "make()", start),
    ]
    assert rows[0]["resolution"] == "resolved"
    assert_unresolved(rows[1], raw)


def test_chunk_metadata_keeps_inner_and_outer_names(tmp_path):
    path, raw = write(
        tmp_path, "def caller(obj):\n    return getattr(obj, 'audit')()\n"
    )
    (chunk,) = chunk_file(path, "python")
    spans = chunk.metadata["call_spans"]
    assert sorted(chunk.metadata["calls"]) == ["getattr", "getattr(obj, 'audit')"]
    start = raw.index(b"getattr")
    outer = next(span for span in spans if span["name"] != "getattr")
    assert outer["raw_reference"] == "getattr(obj, 'audit')"
    assert (outer["callee_start"], outer["callee_end"]) == (
        start,
        raw.index(b")", start) + 1,
    )
    assert (outer["start"], outer["end"]) == (start, raw.rindex(b")") + 1)


def test_non_call_relationships_and_symbols_are_unchanged(tmp_path):
    body = (
        "import os\nfrom pathlib import Path\n\n"
        "def audit():\n    return Path(os.sep)\n\n"
        "def caller(obj):\n    value = getattr(obj, 'audit')@@\n    return audit()\n"
    )
    with_call, _ = write(tmp_path, body.replace("@@", "()"))
    with_call_graph = symbol_graph.extract_symbol_graph(
        with_call, "python", fail_fast=True
    )
    other = tmp_path / "other"
    other.mkdir()
    without_call, _ = write(other, body.replace("@@", "  "))
    without_graph = symbol_graph.extract_symbol_graph(
        without_call, "python", fail_fast=True
    )

    def non_calls(graph):
        return [r for r in graph["relationships"] if r["type"] != "calls"]

    # Dependency targets are unchanged (endpoint IDs are content-based).
    def targets(graph):
        return sorted((r["type"], r["to"]) for r in non_calls(graph))

    assert [kind for kind, _ in targets(with_call_graph)].count("dependencies") == 4
    assert targets(with_call_graph) == targets(without_graph)

    # Chunk content differs by the two call bytes, so compare names and spans.
    def symbols(graph):
        return {
            kind: sorted(
                (row.get("name"), row.get("line"), row.get("end_line")) for row in rows
            )
            for kind, rows in graph["symbols"].items()
        }

    assert symbols(with_call_graph) == symbols(without_graph)
    # Only the outer site is added; the simple local call still resolves.
    added = [
        row["reference"]
        for row in calls(with_call_graph)
        if row["reference"] not in {r["reference"] for r in calls(without_graph)}
    ]
    assert added == ["getattr(obj, 'audit')"]
    local = [row for row in calls(with_call_graph) if row["reference"] == "audit"]
    assert len(local) == 1 and local[0]["resolution"] == "resolved"


@pytest.mark.parametrize("mode", MODES)
def test_parenthesized_callable_return_outer_sites(tmp_path, mode):
    path, raw = write(
        tmp_path,
        "def audit():\n    return 1\n\n"
        "def caller(o, h, g):\n"
        "    (g())()\n"
        "    ((getattr(o, 'audit')))(1)\n"
        "    (  # audit\n        g())()\n"
        "    (g)()\n"
        "    h['audit']()\n",
    )
    rows = calls(
        symbol_graph.extract_symbol_graph(
            path, "python", resolution_mode=mode, fail_fast=True
        )
    )
    plain = raw.index(b"(g())()")
    nested = raw.index(b"((getattr")
    commented = raw.index(b"(  # audit")
    expected = [
        expected_site(raw, "(g())", plain),
        expected_site(raw, "g", plain + 1),
        expected_site(raw, "((getattr(o, 'audit')))", nested),
        expected_site(raw, "getattr", nested + 2),
        expected_site(raw, "(  # audit\n        g())", commented),
        expected_site(raw, "g", raw.index(b"g())()", commented)),
    ]

    def order(site):
        return tuple(site.values())

    # ``(g)()`` (a parenthesized name) and ``h['audit']()`` (a subscript) are
    # not callable-return expressions and stay outside this contract.
    assert sorted(map(observed, rows), key=order) == sorted(expected, key=order)
    caller = owner_id(path, "caller")
    audit = owner_id(path, "audit")
    for row in rows:
        assert row["from"] == caller
        assert_unresolved(row, raw)
        assert audit not in row["candidates"]
    assert len({row["call_site_id"] for row in rows}) == len(rows)
    (chunk,) = [c for c in chunk_file(path, "python") if "caller" in c.content[:12]]
    # Chunk metadata names are the raw callee bytes, parentheses included.
    assert sorted(chunk.metadata["calls"]) == sorted(
        [
            "(g())",
            "g",
            "((getattr(o, 'audit')))",
            "getattr",
            "(  # audit\n        g())",
            "g",
        ]
    )
