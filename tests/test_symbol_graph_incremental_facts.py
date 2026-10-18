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


@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_496_anchor_nfd_path_uses_canonical_definition_identity(
    tmp_path: Path, monkeypatch, mode: str
):
    from chunker.boundary.adapter import extract_boundary_ir
    from chunker.boundary.cache import load_cache_index, load_cache_record

    source = tmp_path / "cafe\u0301.py"
    source.write_text(
        "def serve():\n    return missing()\n",
        encoding="utf-8",
    )

    isolated = extract_symbol_facts_for_file(source, tmp_path, "python")
    graph = extract_symbol_graph(tmp_path, "python", resolution_mode=mode)
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
    assert fact["location"]["start_line"] == fact["location"]["end_line"] == 2
    assert isolated["call_facts"] == graph["call_facts"]
    assert unicodedata.is_normalized("NFD", fact["file"])
    source_bytes = source.read_bytes()
    expected_call = b"missing()"
    expected_start = source_bytes.index(expected_call)
    assert (
        source_bytes[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
        == expected_call
    )
    assert fact["location"] == {
        "byte_start": expected_start,
        "byte_end": expected_start + len(expected_call),
        "start_line": 2,
        "end_line": 2,
    }
    assert (
        source_bytes[fact["callee_byte_start"] : fact["callee_byte_end"]].decode()
        == fact["reference"]
    )

    cache_dir = tmp_path / ".boundary-cache"
    fresh = extract_boundary_ir(tmp_path, "python", resolution_mode=mode)
    cold = extract_boundary_ir(
        tmp_path,
        "python",
        resolution_mode=mode,
        incremental=True,
        cache_dir=cache_dir,
    )
    index = load_cache_index(cache_dir)
    record = load_cache_record(cache_dir, index.records[source.name])
    assert record is not None

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "_extract_file_cache_record",
        lambda *args, **kwargs: pytest.fail("warm NFD facts must be reused"),
    )
    warm = extract_boundary_ir(
        tmp_path,
        "python",
        resolution_mode=mode,
        incremental=True,
        cache_dir=cache_dir,
    )
    for document in (fresh, cold, warm):
        edge = next(
            edge
            for edge in document["edges"]
            if edge["type"] == "calls" and edge["file"] == source.name
        )
        assert edge["id"] == edge["call_site_id"] == fact["id"]
        assert edge["location"] == fact["location"]
    assert record.symbol_facts["call_facts"] == [fact]


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


def test_496_call_site_decorated_method_and_nested_function_use_inner_owner(
    tmp_path: Path,
):
    source = tmp_path / "decorated.py"
    source.write_text(
        "@class_decorate()\n"
        "class Service:\n"
        "    @decorate(factory())\n"
        "    def method(self):\n"
        "        return body()\n\n"
        "@outer_decorate()\n"
        "def outer():\n"
        "    before()\n"
        "    @decorate(factory())\n"
        "    def inner():\n"
        "        return nested()\n"
        "    return inner()\n",
        encoding="utf-8",
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")
    symbols = {
        symbol["name"]: symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
    }
    call_facts = facts["call_facts"]
    assert [fact["reference"] for fact in call_facts] == [
        "class_decorate",
        "decorate",
        "factory",
        "body",
        "outer_decorate",
        "before",
        "decorate",
        "factory",
        "nested",
        "inner",
    ]
    owners = [(fact["reference"], fact["from"]) for fact in call_facts]
    assert owners == [
        ("class_decorate", symbols["Service"]),
        ("decorate", symbols["method"]),
        ("factory", symbols["method"]),
        ("body", symbols["method"]),
        ("outer_decorate", symbols["outer"]),
        ("before", symbols["outer"]),
        ("decorate", symbols["inner"]),
        ("factory", symbols["inner"]),
        ("nested", symbols["inner"]),
        ("inner", symbols["outer"]),
    ]
    assert len({fact["id"] for fact in call_facts}) == len(call_facts)


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
@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_496_call_site_js_repeated_raw_facts_ignore_unrelated_callees(
    tmp_path: Path, language: str, extension: str, mode: str
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

    source_bytes = source.read_bytes()
    cursor = 0
    for fact, expected_call in zip(
        first["call_facts"],
        (b"clock.stamp()", b"stamp()", b"stamp()"),
        strict=True,
    ):
        start = source_bytes.index(expected_call, cursor)
        end = start + len(expected_call)
        cursor = end
        assert (
            source_bytes[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
            == expected_call
        )
        assert fact["location"] == {
            "byte_start": start,
            "byte_end": end,
            "start_line": 1,
            "end_line": 1,
        }
    isolated = assemble_symbol_graph([first], total_files=1, resolution_mode=mode)
    target = tmp_path / f"clock.{extension}"
    target.write_text("export function stamp() { return 1; }\n", encoding="utf-8")
    target_facts = extract_symbol_facts_for_file(target, tmp_path, language)
    second = extract_symbol_facts_for_file(source, tmp_path, language)
    resolved = assemble_symbol_graph(
        [second, target_facts], total_files=2, resolution_mode=mode
    )
    legacy = tmp_path / f"legacy.{extension}"
    legacy.write_text("export function stamp() { return 2; }\n", encoding="utf-8")
    legacy_facts = extract_symbol_facts_for_file(legacy, tmp_path, language)
    ambiguous = assemble_symbol_graph(
        [second, target_facts, legacy_facts], total_files=3, resolution_mode=mode
    )
    legacy.unlink()
    third = extract_symbol_facts_for_file(source, tmp_path, language)
    resolved_again = assemble_symbol_graph(
        [third, target_facts], total_files=2, resolution_mode=mode
    )
    target.unlink()
    fourth = extract_symbol_facts_for_file(source, tmp_path, language)
    removed = assemble_symbol_graph([fourth], total_files=1, resolution_mode=mode)

    for observed in (second, third, fourth):
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
            for fact in observed["call_facts"]
        ]
    expected_ids = [fact["id"] for fact in first["call_facts"]]
    for graph in (isolated, resolved, ambiguous, resolved_again, removed):
        calls = [
            rel
            for rel in graph["relationships"]
            if rel["type"] == "calls" and rel["file"] == source.name
        ]
        assert [rel["call_site_id"] for rel in calls] == expected_ids

    def call_resolutions(graph):
        return {
            relationship["resolution"]
            for relationship in graph["relationships"]
            if relationship["type"] == "calls" and relationship["file"] == source.name
        }

    assert call_resolutions(isolated) == {"unresolved"}
    assert call_resolutions(resolved) == {"resolved"}
    assert call_resolutions(ambiguous) == {"ambiguous"}
    assert call_resolutions(resolved_again) == {"resolved"}
    assert call_resolutions(removed) == {"unresolved"}
    resolved_target = next(iter(target_facts["symbol_lookup"]))
    ambiguous_targets = {
        resolved_target,
        next(iter(legacy_facts["symbol_lookup"])),
    }
    assert all(
        relationship["candidates"] == [resolved_target]
        for relationship in resolved["relationships"]
        if relationship["type"] == "calls" and relationship["file"] == source.name
    )
    assert all(
        set(relationship["candidates"]) == ambiguous_targets
        for relationship in ambiguous["relationships"]
        if relationship["type"] == "calls" and relationship["file"] == source.name
    )


@pytest.mark.parametrize("mode", ["strict", "permissive"])
@pytest.mark.parametrize("owner_kind", ["function", "method"])
def test_496_call_site_typescript_nested_static_calls_keep_raw_sites(
    tmp_path: Path, mode: str, owner_kind: str
):
    source = tmp_path / "now.ts"
    source.write_text(
        (
            "export function now() {\n  return JSON.stringify(Date.now());\n}\n"
            if owner_kind == "function"
            else "export class Clock {\n  now() {\n    return JSON.stringify(Date.now());\n  }\n}\n"
        ),
        encoding="utf-8",
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "typescript")
    owner = next(
        symbol_id
        for symbol_id, symbol in facts["symbol_lookup"].items()
        if symbol["name"] == "now"
    )
    calls = facts["call_facts"]
    isolated = assemble_symbol_graph([facts], total_files=1, resolution_mode=mode)

    assert [fact["reference"] for fact in calls] == ["JSON.stringify", "Date.now"]
    assert all(fact["from"] == owner for fact in calls)
    source_bytes = source.read_bytes()
    expected_line = 2 if owner_kind == "function" else 3
    for fact, expected_call in zip(
        calls, (b"JSON.stringify(Date.now())", b"Date.now()"), strict=True
    ):
        start = source_bytes.index(expected_call)
        end = start + len(expected_call)
        assert (
            source_bytes[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
            == expected_call
        )
        assert fact["location"] == {
            "byte_start": start,
            "byte_end": end,
            "start_line": expected_line,
            "end_line": expected_line,
        }
        assert (
            source_bytes[fact["callee_byte_start"] : fact["callee_byte_end"]].decode()
            == fact["reference"]
        )
    target = tmp_path / "targets.ts"
    target.write_text(
        "export function stringify() { return ''; }\n"
        "export function now() { return 1; }\n",
        encoding="utf-8",
    )
    target_facts = extract_symbol_facts_for_file(target, tmp_path, "typescript")
    resolved = assemble_symbol_graph(
        [facts, target_facts], total_files=2, resolution_mode=mode
    )
    legacy = tmp_path / "legacy.ts"
    legacy.write_text(
        "export function stringify() { return 'legacy'; }\n"
        "export function now() { return 2; }\n",
        encoding="utf-8",
    )
    legacy_facts = extract_symbol_facts_for_file(legacy, tmp_path, "typescript")
    ambiguous = assemble_symbol_graph(
        [facts, target_facts, legacy_facts], total_files=3, resolution_mode=mode
    )
    legacy.unlink()
    after_legacy = extract_symbol_facts_for_file(source, tmp_path, "typescript")
    resolved_again = assemble_symbol_graph(
        [after_legacy, target_facts], total_files=2, resolution_mode=mode
    )
    target.unlink()
    after_targets = extract_symbol_facts_for_file(source, tmp_path, "typescript")
    removed = assemble_symbol_graph(
        [after_targets], total_files=1, resolution_mode=mode
    )

    assert (
        facts["call_facts"] == after_legacy["call_facts"] == after_targets["call_facts"]
    )
    expected_ids = [fact["id"] for fact in calls]
    for graph in (isolated, resolved, ambiguous, resolved_again, removed):
        graph_calls = [
            relationship
            for relationship in graph["relationships"]
            if relationship["type"] == "calls" and relationship["file"] == source.name
        ]
        assert [
            relationship["call_site_id"] for relationship in graph_calls
        ] == expected_ids
    resolved_annotations = {
        relationship["reference"]: relationship["resolution"]
        for relationship in resolved["relationships"]
        if relationship["type"] == "calls" and relationship["file"] == source.name
    }
    assert resolved_annotations == {
        "JSON.stringify": "resolved",
        "Date.now": "ambiguous" if owner_kind == "function" else "resolved",
    }
    assert {
        relationship["resolution"]
        for relationship in ambiguous["relationships"]
        if relationship["type"] == "calls" and relationship["file"] == source.name
    } == {"ambiguous"}
    removed_annotations = {
        relationship["reference"]: relationship["resolution"]
        for relationship in removed["relationships"]
        if relationship["type"] == "calls" and relationship["file"] == source.name
    }
    assert removed_annotations == {
        "JSON.stringify": "unresolved",
        "Date.now": "resolved",
    }


@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_496_call_site_python_qualified_self_collisions_remain_facts(
    tmp_path: Path, mode: str
):
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
    facts = extract_symbol_facts_for_file(source, tmp_path, "python")
    graph = assemble_symbol_graph([facts], total_files=1, resolution_mode=mode)
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

    source_bytes = source.read_bytes()
    expected_calls = (
        b"str(datetime.now())",
        b"datetime.now()",
        b"time.time()",
        b"recur()",
    )
    for fact, expected_call, expected_line in zip(
        facts["call_facts"], expected_calls, (2, 2, 5, 8), strict=True
    ):
        start = source_bytes.rindex(expected_call)
        end = start + len(expected_call)
        assert (
            source_bytes[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
            == expected_call
        )
        assert fact["location"] == {
            "byte_start": start,
            "byte_end": end,
            "start_line": expected_line,
            "end_line": expected_line,
        }

    other = tmp_path / "other.py"
    other.write_text(
        "def now():\n    return 1\n\ndef time():\n    return 2\n",
        encoding="utf-8",
    )
    other_facts = extract_symbol_facts_for_file(other, tmp_path, "python")
    with_targets = extract_symbol_facts_for_file(source, tmp_path, "python")
    ambiguous = assemble_symbol_graph(
        [with_targets, other_facts], total_files=2, resolution_mode=mode
    )
    other.unlink()
    after_removal = extract_symbol_facts_for_file(source, tmp_path, "python")
    restored = assemble_symbol_graph(
        [after_removal], total_files=1, resolution_mode=mode
    )

    assert (
        facts["call_facts"] == with_targets["call_facts"] == after_removal["call_facts"]
    )
    expected_ids = [fact["id"] for fact in facts["call_facts"]]
    for observed in (graph, ambiguous, restored):
        assert [
            relationship["call_site_id"]
            for relationship in observed["relationships"]
            if relationship["type"] == "calls" and relationship["file"] == source.name
        ] == expected_ids
    assert {
        relationship["reference"]
        for relationship in ambiguous["relationships"]
        if relationship["type"] == "calls" and relationship["resolution"] == "ambiguous"
    } == {"datetime.now", "time.time"}


@pytest.mark.parametrize("mode", ["strict", "permissive"])
@pytest.mark.parametrize("fail_fast", [False, True])
@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize(
    ("callee", "padding"),
    [("target", "\n" * 16), ("target", ""), ("你好", "\n" * 16)],
    ids=["wrong-reference", "end-of-file", "unicode-reference"],
)
def test_496_call_sites_use_the_replacement_decoded_parser_buffer(
    tmp_path: Path,
    monkeypatch,
    mode: str,
    fail_fast: bool,
    language: str,
    callee: str,
    padding: str,
):
    from chunker.boundary import adapter, extract_boundary_ir

    if language == "python":
        source = tmp_path / "caller.py"
        definition = f"def caller():\n    {callee}()\n{padding}".encode("utf-8")
        raw_prefix = b"# \xff\n"
        parsed_prefix = b"# \xef\xbf\xbd\n"
    else:
        source = tmp_path / "caller.js"
        definition = f"function caller() {{\n    {callee}();\n}}\n{padding}".encode(
            "utf-8"
        )
        raw_prefix = b"// \xff\n"
        parsed_prefix = b"// \xef\xbf\xbd\n"
    source.write_bytes(raw_prefix + definition)
    expected_buffer = parsed_prefix + definition
    expected_callee = callee.encode("utf-8")
    expected_call = expected_callee + b"()"
    start = expected_buffer.index(expected_call)
    expected_location = {
        "byte_start": start,
        "byte_end": start + len(expected_call),
        "start_line": 3,
        "end_line": 3,
    }

    isolated = extract_symbol_facts_for_file(
        source, tmp_path, language, fail_fast=fail_fast
    )
    assert isolated["errors"] == []
    assert len(isolated["call_facts"]) == 1
    fact = isolated["call_facts"][0]
    assert fact["reference"] == callee
    assert fact["location"] == expected_location
    assert (
        expected_buffer[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
        == expected_call
    )
    assert (
        expected_buffer[fact["callee_byte_start"] : fact["callee_byte_end"]]
        == expected_callee
    )

    graph = extract_symbol_graph(
        tmp_path, language, resolution_mode=mode, fail_fast=fail_fast
    )
    assert graph["call_facts"] == isolated["call_facts"]

    cache_dir = tmp_path / ".boundary-cache"
    fresh = extract_boundary_ir(
        tmp_path, language, resolution_mode=mode, fail_fast=fail_fast
    )
    cold = extract_boundary_ir(
        tmp_path,
        language,
        resolution_mode=mode,
        fail_fast=fail_fast,
        incremental=True,
        cache_dir=cache_dir,
    )
    monkeypatch.setattr(
        adapter,
        "_extract_file_cache_record",
        lambda *args, **kwargs: pytest.fail(
            "warm replacement-decoded call facts must be reused"
        ),
    )
    warm = extract_boundary_ir(
        tmp_path,
        language,
        resolution_mode=mode,
        fail_fast=fail_fast,
        incremental=True,
        cache_dir=cache_dir,
    )
    for document in (fresh, cold, warm):
        edges = [edge for edge in document["edges"] if edge["type"] == "calls"]
        assert len(edges) == 1
        edge = edges[0]
        assert edge["id"] == edge["call_site_id"] == fact["id"]
        assert edge["reference"] == callee
        assert edge["location"] == expected_location
        assert edge["file"] == edge["metadata"]["file"] == source.name


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("many_lines", [False, True], ids=["minified", "many-lines"])
def test_496_call_site_line_lookup_avoids_repeated_prefix_scans(
    tmp_path: Path,
    monkeypatch,
    language: str,
    newline: bytes,
    many_lines: bool,
):
    from chunker import symbol_graph as graph_module

    count = 256
    if language == "python":
        source = tmp_path / "caller.py"
        prefix = b"# caf\xc3\xa9" + newline + b"def caller():" + newline
        indentation = b"    "
        suffix = b""
    else:
        source = tmp_path / "caller.js"
        prefix = b"// caf\xc3\xa9" + newline + b"function caller() {" + newline
        indentation = b"  "
        suffix = b"}" + newline
    if many_lines:
        body = (indentation + b"f();" + newline) * count
    else:
        body = indentation + b"f();" * count + newline
    raw = prefix + body + suffix
    source.write_bytes(raw)
    measured = {
        "prefix_count_and_slice_bytes": 0,
        "buffers": 0,
        "newline_index_scans": 0,
        "newline_index_scan_bytes": 0,
    }

    class BudgetBytes(bytes):
        def count(self, sub, start=0, end=None):
            stop = len(self) if end is None else end
            measured["prefix_count_and_slice_bytes"] += stop - start
            return super().count(sub, start, stop)

        def __getitem__(self, key):
            if isinstance(key, slice):
                measured["prefix_count_and_slice_bytes"] += len(
                    range(*key.indices(len(self)))
                )
            return super().__getitem__(key)

    original = graph_module._call_facts_for_chunks
    original_finditer = graph_module.re.finditer

    def instrument_index(pattern, buffer, *args, **kwargs):
        if pattern == b"\n" and isinstance(buffer, BudgetBytes):
            measured["newline_index_scans"] += 1
            measured["newline_index_scan_bytes"] += len(buffer)
        return original_finditer(pattern, buffer, *args, **kwargs)

    def instrument(chunks, owners, buffer, display_file):
        measured["buffers"] += 1
        return original(chunks, owners, BudgetBytes(buffer), display_file)

    monkeypatch.setattr(graph_module, "_call_facts_for_chunks", instrument)
    monkeypatch.setattr(graph_module.re, "finditer", instrument_index)
    facts = extract_symbol_facts_for_file(source, tmp_path, language)
    calls = facts["call_facts"]
    assert len(calls) == count
    assert len({fact["id"] for fact in calls}) == count
    for index, fact in enumerate(calls):
        stride = len(indentation) + 4 + len(newline) if many_lines else 4
        start = len(prefix) + len(indentation) + index * stride
        expected_line = 3 + index if many_lines else 3
        assert fact["reference"] == "f"
        assert raw[fact["callee_byte_start"] : fact["callee_byte_end"]] == b"f"
        assert (
            raw[fact["location"]["byte_start"] : fact["location"]["byte_end"]] == b"f()"
        )
        assert fact["location"] == {
            "byte_start": start,
            "byte_end": start + 3,
            "start_line": expected_line,
            "end_line": expected_line,
        }
    assert measured["buffers"] == 1
    assert measured["prefix_count_and_slice_bytes"] <= 2 * len(raw)
    assert measured["newline_index_scans"] == 1
    assert measured["newline_index_scan_bytes"] == len(raw)


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_496_line_index_preserves_nested_multiline_call_spans(
    tmp_path: Path,
    language: str,
    newline: bytes,
):
    if language == "python":
        source = tmp_path / "caller.py"
        prefix = b"# caf\xc3\xa9" + newline + b"def caller():" + newline + b"    "
        suffix = newline
    else:
        source = tmp_path / "caller.js"
        prefix = (
            b"// caf\xc3\xa9" + newline + b"function caller() {" + newline + b"    "
        )
        suffix = b";" + newline + b"}" + newline
    inner = b"g('caf\xc3\xa9')"
    outer = b"f(" + newline + b"        " + inner + newline + b"    )"
    raw = prefix + outer + suffix
    source.write_bytes(raw)
    facts = extract_symbol_facts_for_file(source, tmp_path, language)
    calls = facts["call_facts"]
    assert len(calls) == 2
    for fact, reference, expected_call, start_line, end_line in zip(
        calls,
        ("f", "g"),
        (outer, inner),
        (3, 4),
        (5, 4),
        strict=True,
    ):
        start = raw.index(expected_call)
        assert fact["reference"] == reference
        assert (
            raw[fact["callee_byte_start"] : fact["callee_byte_end"]]
            == reference.encode()
        )
        assert (
            raw[fact["location"]["byte_start"] : fact["location"]["byte_end"]]
            == expected_call
        )
        assert fact["location"] == {
            "byte_start": start,
            "byte_end": start + len(expected_call),
            "start_line": start_line,
            "end_line": end_line,
        }
