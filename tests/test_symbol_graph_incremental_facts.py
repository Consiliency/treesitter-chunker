import unicodedata
from pathlib import Path

import pytest

from chunker.types import CodeChunk
from chunker.symbol_graph import (
    _call_site_id,
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)


def _assert_496_sources_match_files(graph: dict, symbol_name: str) -> None:
    symbols = {
        symbol_id: symbol
        for symbol_id, symbol in graph["symbol_lookup"].items()
        if symbol["name"] == symbol_name
    }
    assert len(symbols) == 2
    assert len(set(symbols)) == 2
    assert all(
        symbol["definition_id"] in symbol_id for symbol_id, symbol in symbols.items()
    )
    assert graph["relationships"]
    for relationship in graph["relationships"]:
        assert relationship["from"] in graph["symbol_lookup"]
        source = graph["symbol_lookup"][relationship["from"]]
        assert source["file"] == relationship["file"]


def test_symbol_facts_include_reusable_file_fields(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        """def run():
    import os
    return os.getcwd()
""",
        encoding="utf-8",
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")

    assert facts["display_file"] == "service.py"
    assert facts["path"] == "service.py"
    assert facts["module"] == "service"
    assert facts["language"] == "python"
    assert facts["symbol_lookup"]
    assert facts["import_strings"]
    assert facts["chunk_records"]
    assert facts["errors"] == []


def test_assemble_symbol_facts_matches_extract_symbol_graph(tmp_path: Path):
    (tmp_path / "helper.py").write_text(
        "class Helper:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "service.py").write_text(
        """from helper import Helper

def build():
    return Helper()
""",
        encoding="utf-8",
    )

    facts = [
        extract_symbol_facts_for_file(path, tmp_path, "python")
        for path in collect_source_files(tmp_path, "python")
    ]

    assembled = assemble_symbol_graph(
        facts,
        total_files=2,
        resolution_mode="permissive",
    )
    direct = extract_symbol_graph(tmp_path, "python", resolution_mode="permissive")

    assert assembled == direct


def test_assemble_symbol_graph_preserves_sorted_resolution_candidates(tmp_path: Path):
    (tmp_path / "a.py").write_text("def target():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def target():\n    return 2\n", encoding="utf-8")
    (tmp_path / "use.py").write_text(
        "def caller():\n    return target()\n",
        encoding="utf-8",
    )

    graph = extract_symbol_graph(tmp_path, "python", resolution_mode="strict")
    ambiguous = [
        rel for rel in graph["relationships"] if rel["resolution"] == "ambiguous"
    ]

    assert ambiguous
    assert all(rel["candidates"] == sorted(rel["candidates"]) for rel in ambiguous)


def test_496_anchor_module_and_package_definitions_survive(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "pkg.py").write_text(
        "def run():\n    return sorted([])\n", encoding="utf-8"
    )
    (package / "__init__.py").write_text(
        "import time\ndef run():\n    return time.time()\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path, "python")

    _assert_496_sources_match_files(graph, "run")
    call_files = {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    }
    assert call_files == {("sorted", "pkg.py"), ("time.time", "pkg/__init__.py")}


def test_496_anchor_typescript_and_tsx_definitions_survive(tmp_path: Path):
    (tmp_path / "x.ts").write_text(
        "export function f() { return g(); }\n", encoding="utf-8"
    )
    (tmp_path / "x.tsx").write_text(
        "export function f() { return k(); }\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path)

    _assert_496_sources_match_files(graph, "f")
    assert {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == {("g", "x.ts"), ("k", "x.tsx")}


def test_496_anchor_identical_python_calls_survive_reversed_fact_order(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    source = "def run():\n    return sorted([])\n"
    (tmp_path / "pkg.py").write_text(source, encoding="utf-8")
    (package / "__init__.py").write_text(source, encoding="utf-8")
    paths = [tmp_path / "pkg.py", package / "__init__.py"]
    facts = [extract_symbol_facts_for_file(path, tmp_path, "python") for path in paths]

    graphs = (
        assemble_symbol_graph(facts, total_files=2),
        assemble_symbol_graph(list(reversed(facts)), total_files=2),
    )

    for graph in graphs:
        _assert_496_sources_match_files(graph, "run")
        calls = {
            (relationship["from"], relationship["reference"], relationship["file"])
            for relationship in graph["relationships"]
            if relationship["type"] == "calls"
        }
        assert len(calls) == 2
        assert {(reference, file) for _, reference, file in calls} == {
            ("sorted", "pkg.py"),
            ("sorted", "pkg/__init__.py"),
        }
    assert graphs[0]["symbol_lookup"] == graphs[1]["symbol_lookup"]
    assert {
        (item["from"], item["to"], item["type"], item["reference"], item["file"])
        for item in graphs[0]["relationships"]
    } == {
        (item["from"], item["to"], item["type"], item["reference"], item["file"])
        for item in graphs[1]["relationships"]
    }


def test_496_anchor_identical_typescript_and_tsx_calls_survive(tmp_path: Path):
    source = "export function f() { return shared(); }\n"
    (tmp_path / "x.ts").write_text(source, encoding="utf-8")
    (tmp_path / "x.tsx").write_text(source, encoding="utf-8")

    graph = extract_symbol_graph(tmp_path)

    _assert_496_sources_match_files(graph, "f")
    calls = [
        relationship
        for relationship in graph["relationships"]
        if relationship["type"] == "calls" and relationship["reference"] == "shared"
    ]
    assert len(calls) == 2
    assert {relationship["file"] for relationship in calls} == {"x.ts", "x.tsx"}


def test_496_anchor_dotted_directory_and_file_definitions_survive(tmp_path: Path):
    nested = tmp_path / "src" / "api"
    nested.mkdir(parents=True)
    (nested / "client.ts").write_text(
        "export function send() { return nestedCall(); }\n", encoding="utf-8"
    )
    (tmp_path / "src" / "api.client.ts").write_text(
        "export function send() { return dottedCall(); }\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path, "typescript")

    _assert_496_sources_match_files(graph, "send")
    assert {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == {
        ("nestedCall", "src/api/client.ts"),
        ("dottedCall", "src/api.client.ts"),
    }


def test_496_anchor_nfd_module_and_package_paths_are_preserved(tmp_path: Path):
    module = unicodedata.normalize("NFD", "café")
    package = tmp_path / module
    package.mkdir()
    source = "def serve():\n    return sorted([])\n"
    (tmp_path / f"{module}.py").write_text(source, encoding="utf-8")
    (package / "__init__.py").write_text(source, encoding="utf-8")

    graph = extract_symbol_graph(tmp_path, "python")

    _assert_496_sources_match_files(graph, "serve")
    expected_paths = {f"{module}.py", f"{module}/__init__.py"}
    assert {
        relationship["file"]
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == expected_paths
    assert all(unicodedata.is_normalized("NFD", path) for path in expected_paths)


def test_496_anchor_occurrence_counts_chunks_before_graph_filter(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "sample.py"
    source.write_text("def keep():\n    pass\n", encoding="utf-8")

    def chunk(metadata: dict, node_id: str) -> CodeChunk:
        value = CodeChunk(
            language="python",
            file_path="sample.py",
            node_type="function_definition",
            start_line=1,
            end_line=2,
            byte_start=0,
            byte_end=20,
            parent_context="",
            content="def keep():\n    pass\n",
            node_id=node_id,
            metadata=metadata,
        )
        value.definition_id = "shared-definition"
        return value

    chunks = [
        chunk(
            {"symbol": "filtered", "kind": "variable", "qualified_name": "filtered"},
            "node-filtered",
        ),
        chunk(
            {"symbol": "keep", "kind": "function", "qualified_name": "keep"},
            "node-keep",
        ),
    ]
    monkeypatch.setattr(
        "chunker.symbol_graph.chunk_file", lambda *args, **kwargs: chunks
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")

    assert list(facts["symbol_lookup"]) == ["shared-definition#1"]


def test_496_anchor_unrelated_callee_does_not_change_caller_source(tmp_path: Path):
    caller_path = tmp_path / "caller.py"
    caller_path.write_text(
        "def caller():\n    return target()\n",
        encoding="utf-8",
    )
    first = extract_symbol_graph(tmp_path, "python")
    first_source = next(
        relationship["from"]
        for relationship in first["relationships"]
        if relationship["reference"] == "target"
    )

    (tmp_path / "unrelated.py").write_text(
        "def target():\n    return 1\n",
        encoding="utf-8",
    )
    second = extract_symbol_graph(tmp_path, "python")
    second_edge = next(
        relationship
        for relationship in second["relationships"]
        if relationship["file"] == "caller.py" and relationship["reference"] == "target"
    )

    assert second_edge["from"] == first_source
    assert second["symbol_lookup"][first_source]["file"] == "caller.py"


def test_496_anchor_nfd_path_uses_canonical_definition_identity(tmp_path: Path):
    source = tmp_path / "cafe\u0301.py"
    source.write_text(
        "def serve():\n    return missing()\n",
        encoding="utf-8",
    )

    graph = extract_symbol_graph(source, "python")
    symbol_id, symbol = next(iter(graph["symbol_lookup"].items()))
    relationship = next(
        item
        for item in graph["relationships"]
        if item["type"] == "calls" and item["reference"] == "missing"
    )

    assert symbol["file"] == source.name
    assert symbol_id == symbol["definition_id"]
    assert relationship["from"] == symbol_id
    assert relationship["file"] == source.name
    fact = graph["call_facts"][0]
    assert fact["file"] == source.name
    assert fact["from"] == symbol_id
    assert fact["reference"] == "missing"
    assert fact["id"] == relationship["call_site_id"]


def test_496_call_site_fixed_id_vector():
    assert (
        _call_site_id("caller-id", "src/app.py", 10, 18, 10, 16, "target")
        == "call:db4aa2584c80ce295d03d6b5c1ce7f1b6dea99a2"
    )


def test_496_call_site_raw_facts_preserve_self_repetition_and_decorator_owner(
    tmp_path: Path,
):
    source = tmp_path / "service.py"
    source.write_text(
        "@decorate(factory())\n"
        "def recur():\n"
        "    obj.sub.now(); recur(); recur()\n",
        encoding="utf-8",
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")
    graph = assemble_symbol_graph([facts], total_files=1)
    caller_id = next(iter(facts["symbol_lookup"]))
    call_facts = facts["call_facts"]

    assert [fact["reference"] for fact in call_facts] == [
        "decorate",
        "factory",
        "obj.sub.now",
        "recur",
        "recur",
    ]
    assert all(fact["from"] == caller_id for fact in call_facts)
    assert len({fact["id"] for fact in call_facts}) == 5
    assert all(
        fact["id"].startswith("call:") and len(fact["id"]) == 45 for fact in call_facts
    )
    assert [
        rel["call_site_id"] for rel in graph["relationships"] if rel["type"] == "calls"
    ] == [fact["id"] for fact in call_facts]
    assert graph["call_facts"] == call_facts

    source_bytes = source.read_bytes()
    for fact in call_facts:
        location = fact["location"]
        assert (
            source_bytes[fact["callee_byte_start"] : fact["callee_byte_end"]].decode()
            == fact["reference"]
        )
        assert source_bytes[location["byte_start"] : location["byte_end"]]
        assert fact["type"] == "calls"


def test_496_call_site_raw_facts_do_not_change_with_unrelated_target(
    tmp_path: Path,
):
    source = tmp_path / "caller.py"
    source.write_text("def caller():\n    return target()\n", encoding="utf-8")
    first = extract_symbol_facts_for_file(source, tmp_path, "python")["call_facts"]
    (tmp_path / "target.py").write_text(
        "def target():\n    return 1\n", encoding="utf-8"
    )
    second = extract_symbol_facts_for_file(source, tmp_path, "python")["call_facts"]

    assert first == second


def test_496_call_site_nested_call_uses_smallest_callable_owner(tmp_path: Path):
    source = tmp_path / "nested.py"
    source.write_text(
        "def outer():\n"
        "    def inner():\n"
        "        return target()\n"
        "    return inner()\n",
        encoding="utf-8",
    )
    facts = extract_symbol_facts_for_file(source, tmp_path, "python")
    symbols = {
        symbol["name"]: symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
    }
    owners = {fact["reference"]: fact["from"] for fact in facts["call_facts"]}

    assert owners == {"target": symbols["inner"], "inner": symbols["outer"]}


def test_496_call_site_utf8_crlf_uses_absolute_byte_and_line_oracles(tmp_path: Path):
    source = tmp_path / "unicode.py"
    source_bytes = 'def caller():\r\n    label = "café"; obj . now()\r\n'.encode(
        "utf-8"
    )
    source.write_bytes(source_bytes)

    fact = extract_symbol_facts_for_file(source, tmp_path, "python")["call_facts"][0]

    assert fact["reference"] == "obj . now"
    assert (
        source_bytes[fact["callee_byte_start"] : fact["callee_byte_end"]].decode(
            "utf-8"
        )
        == "obj . now"
    )
    assert (
        source_bytes[
            fact["location"]["byte_start"] : fact["location"]["byte_end"]
        ].decode("utf-8")
        == "obj . now()"
    )
    assert fact["location"]["start_line"] == fact["location"]["end_line"] == 2


@pytest.mark.parametrize(
    ("language", "extension"), [("javascript", "js"), ("typescript", "ts")]
)
def test_496_call_site_js_repeated_raw_facts_ignore_unrelated_callees(
    tmp_path: Path, language: str, extension: str
):
    source = tmp_path / f"caller.{extension}"
    source.write_text(
        "export function caller() { clock.stamp(); stamp(); stamp(); }\n",
        encoding="utf-8",
    )
    first = extract_symbol_facts_for_file(source, tmp_path, language)
    first_projection = [
        (
            fact["id"],
            fact["from"],
            fact["file"],
            fact["reference"],
            fact["location"],
            fact["callee_byte_start"],
            fact["callee_byte_end"],
        )
        for fact in first["call_facts"]
    ]
    assert [fact["reference"] for fact in first["call_facts"]] == [
        "clock.stamp",
        "stamp",
        "stamp",
    ]

    target = tmp_path / f"legacy.{extension}"
    target.write_text("export function stamp() { return 1; }\n", encoding="utf-8")
    target_facts = extract_symbol_facts_for_file(target, tmp_path, language)
    second = extract_symbol_facts_for_file(source, tmp_path, language)
    full = assemble_symbol_graph([second, target_facts], total_files=2)

    assert first_projection == [
        (
            fact["id"],
            fact["from"],
            fact["file"],
            fact["reference"],
            fact["location"],
            fact["callee_byte_start"],
            fact["callee_byte_end"],
        )
        for fact in second["call_facts"]
    ]
    assert [
        rel["call_site_id"]
        for rel in full["relationships"]
        if rel["type"] == "calls" and rel["file"] == source.name
    ] == [fact["id"] for fact in second["call_facts"]]


def test_496_call_site_python_qualified_self_collisions_remain_facts(tmp_path: Path):
    source = tmp_path / "self_calls.py"
    source.write_text(
        "def now():\n"
        "    return str(datetime.now())\n\n"
        "def time():\n"
        "    return time.time()\n\n"
        "def recur():\n"
        "    return recur()\n",
        encoding="utf-8",
    )
    graph = extract_symbol_graph(source, "python")
    calls = [rel for rel in graph["relationships"] if rel["type"] == "calls"]

    assert [fact["reference"] for fact in graph["call_facts"]] == [
        "str",
        "datetime.now",
        "time.time",
        "recur",
    ]
    assert len(calls) == 4
    assert {rel["reference"] for rel in calls if rel["to"] == rel["from"]} == {
        "datetime.now",
        "time.time",
        "recur",
    }
