"""The opt-in call-resolution surface (treesitter-chunker#682, plan 4).

Types, keyword-only parameters, ``language_filter``, the ``ParserInitError``
fallback, CLI flags, ``run.options``, the provenance copy, the schema and spec
text, and the experimental label.
"""

from __future__ import annotations

import argparse
import inspect
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import jsonschema
import pytest
from typer.testing import CliRunner

from chunker import symbol_graph
from chunker.boundary import adapter, dumps_boundary_ir, extract_boundary_ir
from chunker.boundary import types as boundary_types
from chunker.exceptions import ParserInitError
from chunker.symbol_graph import (
    assemble_symbol_graph,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)
from chunker.types import CALL_RESOLUTION_MODES, CallResolution
from tests import call_resolution_harness as harness

ROOT = harness.ROOT
FIXTURES = harness.FIXTURES
KIND_FILTER = FIXTURES / "authored" / "ts-kind-filter"
MODE = "structural"


def test_types_and_reexport() -> None:
    assert CALL_RESOLUTION_MODES == ("name", "structural")
    assert get_args(CallResolution) == CALL_RESOLUTION_MODES
    assert boundary_types.CALL_RESOLUTION_MODES is CALL_RESOLUTION_MODES
    assert boundary_types.CallResolution is CallResolution
    assert {"CALL_RESOLUTION_MODES", "CallResolution"} <= set(boundary_types.__all__)


@pytest.mark.parametrize(
    "function",
    [
        extract_symbol_graph,
        extract_symbol_facts_for_file,
        assemble_symbol_graph,
        extract_boundary_ir,
        adapter._extract_boundary_ir_incremental,
        adapter._extract_file_cache_record,
        adapter._cache_key_payload,
        adapter._assemble_boundary_ir,
    ],
)
def test_call_resolution_is_keyword_only_and_defaults_to_name(
    function: Callable[..., Any],
) -> None:
    parameter = inspect.signature(function).parameters["call_resolution"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default == "name"


def test_language_filter_is_keyword_only() -> None:
    parameter = inspect.signature(assemble_symbol_graph).parameters["language_filter"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


@pytest.mark.parametrize("value", ["imports", "scoped", "", None, "STRUCTURAL"])
def test_unknown_values_raise(value: object, tmp_path: Path) -> None:
    source = KIND_FILTER / "x.ts"
    for call in (
        lambda: extract_symbol_graph(KIND_FILTER, call_resolution=value),
        lambda: extract_symbol_facts_for_file(
            source, KIND_FILTER, call_resolution=value
        ),
        lambda: assemble_symbol_graph([], call_resolution=value),
        lambda: extract_boundary_ir(KIND_FILTER, call_resolution=value),
        lambda: extract_boundary_ir(
            KIND_FILTER,
            call_resolution=value,
            incremental=True,
            cache_dir=tmp_path / "cache",
        ),
    ):
        with pytest.raises(ValueError, match="call_resolution"):
            call()


def test_on_mode_assembly_requires_scope_facts() -> None:
    facts = [
        extract_symbol_facts_for_file(path, KIND_FILTER)
        for path in sorted(KIND_FILTER.iterdir())
    ]
    assert "scope_facts" not in facts[0]
    with pytest.raises(ValueError, match="scope_facts"):
        assemble_symbol_graph(facts, call_resolution=MODE)
    on_facts = [
        extract_symbol_facts_for_file(path, KIND_FILTER, call_resolution=MODE)
        for path in sorted(KIND_FILTER.iterdir())
    ]
    on_facts[0]["scope_facts"]["supported"] = "yes"
    with pytest.raises(ValueError, match="scope_facts"):
        assemble_symbol_graph(on_facts, call_resolution=MODE)
    with pytest.raises(ValueError, match="language_filter"):
        assemble_symbol_graph([], language_filter=3)  # type: ignore[arg-type]


def test_off_mode_facts_have_no_scope_facts() -> None:
    for call_resolution in (None, "name"):
        kwargs = {} if call_resolution is None else {"call_resolution": call_resolution}
        facts = extract_symbol_facts_for_file(
            KIND_FILTER / "x.ts", KIND_FILTER, **kwargs
        )
        assert "scope_facts" not in facts


def _spy_assembly(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    original = symbol_graph.assemble_symbol_graph

    def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        seen.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(symbol_graph, "assemble_symbol_graph", spy)
    monkeypatch.setattr(adapter, "assemble_symbol_graph", spy)
    return seen


@pytest.mark.parametrize("language", [None, "typescript"])
def test_language_filter_reaches_assembly_on_every_path(
    language: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _spy_assembly(monkeypatch)
    extract_symbol_graph(KIND_FILTER, language, call_resolution=MODE)
    extract_boundary_ir(KIND_FILTER, language, call_resolution=MODE)
    extract_boundary_ir(
        KIND_FILTER,
        language,
        call_resolution=MODE,
        incremental=True,
        cache_dir=tmp_path / "cache",
    )
    assert [(item["language_filter"], item["call_resolution"]) for item in seen] == [
        (language, MODE)
    ] * 3


def test_parser_init_fallback_passes_call_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback re-enters ``extract_boundary_ir`` with the same mode (4.2)."""
    cold = extract_boundary_ir(KIND_FILTER, call_resolution=MODE)

    def fail(language: str | None) -> str:
        raise ParserInitError(str(language), "injected")

    monkeypatch.setattr(adapter, "_grammar_version", fail)
    seen = _spy_assembly(monkeypatch)
    fallback = extract_boundary_ir(
        KIND_FILTER,
        call_resolution=MODE,
        incremental=True,
        cache_dir=tmp_path / "cache",
    )
    assert seen and all(item["call_resolution"] == MODE for item in seen)
    assert fallback["run"]["options"]["call_resolution"] == MODE
    assert dumps_boundary_ir(fallback) == dumps_boundary_ir(cold)
    assert not (tmp_path / "cache").exists()


def test_name_is_byte_identical_to_omitting_the_option(tmp_path: Path) -> None:
    omitted = extract_boundary_ir(KIND_FILTER)
    named = extract_boundary_ir(KIND_FILTER, call_resolution="name")
    assert dumps_boundary_ir(named) == dumps_boundary_ir(omitted)
    assert "call_resolution" not in named["run"]["options"]
    incremental = extract_boundary_ir(
        KIND_FILTER,
        call_resolution="name",
        incremental=True,
        cache_dir=tmp_path / "cache",
    )
    assert dumps_boundary_ir(incremental) == dumps_boundary_ir(omitted)
    graph = extract_symbol_graph(KIND_FILTER, call_resolution="name")
    assert "call_resolution" not in graph["metadata"]


def test_on_mode_records_the_mode_and_copies_provenance() -> None:
    graph = extract_symbol_graph(KIND_FILTER, call_resolution=MODE)
    assert graph["metadata"]["call_resolution"] == MODE
    (call,) = (edge for edge in graph["relationships"] if edge["type"] == "calls")
    assert call["provenance"]["call_resolution"] == MODE
    assert call["provenance"]["call_rules"] == ["t1.kind"]
    for edge in graph["relationships"]:
        if edge is not call:
            assert "call_rules" not in edge["provenance"]
    for resolution_mode in ("strict", "permissive"):
        ir = extract_boundary_ir(
            KIND_FILTER, resolution_mode=resolution_mode, call_resolution=MODE
        )
        assert ir["run"]["options"]["call_resolution"] == MODE
        (edge,) = (edge for edge in ir["edges"] if edge["type"] == "calls")
        assert edge["provenance"]["call_resolution"] == MODE
        assert edge["provenance"]["call_rules"] == ["t1.kind"]
        assert edge["provenance"]["resolution_mode"] == resolution_mode
        assert edge["resolution"] == "ambiguous"
        assert edge["metadata"]["is_internal"] is False
        assert len(edge["candidates"]) == 2
        for other in ir["edges"]:
            if other is not edge:
                assert "call_resolution" not in other["provenance"]


def test_no_source_files_metadata_records_the_mode(tmp_path: Path) -> None:
    graph = extract_symbol_graph(tmp_path, call_resolution=MODE)
    assert graph["metadata"]["call_resolution"] == MODE
    assert "call_resolution" not in extract_symbol_graph(tmp_path)["metadata"]


def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(
        (ROOT / "chunker" / "boundary" / "boundary_ir.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return jsonschema.Draft202012Validator(schema)


def test_schema_documents_the_additive_keys() -> None:
    validator = _validator()
    ir = extract_boundary_ir(KIND_FILTER, call_resolution=MODE)
    assert ir["schema_version"] == "3.0"
    validator.validate(ir)
    for path, value in (
        (("run", "options", "call_resolution"), "imports"),
        (("run", "options", "call_resolution"), "name"),
    ):
        broken = json.loads(json.dumps(ir))
        broken[path[0]][path[1]][path[2]] = value
        assert list(validator.iter_errors(broken))
    for key, value in (
        ("call_resolution", "bogus"),
        ("call_rules", []),
        ("call_rules", "t1.kind"),
    ):
        broken = json.loads(json.dumps(ir))
        edge = next(edge for edge in broken["edges"] if edge["type"] == "calls")
        edge["provenance"][key] = value
        assert list(validator.iter_errors(broken)), (key, value)


def test_cli_symbols_extract_flag(tmp_path: Path) -> None:
    from chunker.cli.symbol_commands import cmd_extract_symbols, setup_symbol_parser

    parser = argparse.ArgumentParser()
    setup_symbol_parser(parser.add_subparsers(dest="command"))
    help_text = parser._subparsers._group_actions[0].choices["symbols"]  # type: ignore[union-attr]
    extract = help_text._subparsers._group_actions[0].choices["extract"]
    assert "Experimental" in extract.format_help()
    defaults = parser.parse_args(["symbols", "extract", str(KIND_FILTER)])
    assert defaults.call_resolution == "name"
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["symbols", "extract", str(KIND_FILTER), "--call-resolution", "imports"]
        )
    output = tmp_path / "out.json"
    args = parser.parse_args(
        [
            "symbols",
            "extract",
            str(KIND_FILTER),
            "-l",
            "typescript",
            "--call-resolution",
            MODE,
            "-o",
            str(output),
        ]
    )
    assert cmd_extract_symbols(args) == 0
    graph = json.loads(output.read_text(encoding="utf-8"))
    assert graph["metadata"]["call_resolution"] == MODE


def test_cli_boundary_flag(tmp_path: Path) -> None:
    from cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["boundary", "--help"])
    assert result.exit_code == 0
    assert "--call-resolution" in result.output
    assert "Experimental" in result.output
    root = tmp_path / "tree"
    shutil.copytree(KIND_FILTER, root)
    outputs = {}
    for mode in ("name", MODE):
        output = tmp_path / f"{mode}.json"
        result = runner.invoke(
            app,
            ["boundary", str(root), "--call-resolution", mode, "-o", str(output), "-q"],
        )
        assert result.exit_code == 0, result.output
        outputs[mode] = json.loads(output.read_text(encoding="utf-8"))
    assert "call_resolution" not in outputs["name"]["run"]["options"]
    assert outputs[MODE]["run"]["options"]["call_resolution"] == MODE
    result = runner.invoke(app, ["boundary", str(root), "--call-resolution", "imports"])
    assert result.exit_code != 0


def test_experimental_label_and_spec_text() -> None:
    for function in (extract_symbol_graph, extract_boundary_ir):
        assert "experimental" in (function.__doc__ or "").lower()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert "**Experimental:**" in unreleased
    assert "call_resolution" in unreleased
    assert "resolves nothing" in unreleased
    spec = (ROOT / "docs" / "interface-boundary-spec.md").read_text(encoding="utf-8")
    assert "### Call resolution extension (experimental)" in spec
    assert "Resolution remains heuristic and does not\nestablish" not in spec
    for phrase in ("consumers key edges on `id`", "parity_digest", "run.options"):
        assert phrase in spec
