"""Same-version Boundary v3 migration for physical source rows."""

import hashlib
import json
from unittest.mock import patch

import pytest

from chunker import core, symbol_graph
from chunker.boundary import adapter
from chunker.boundary.cache import load_cache_index


@pytest.fixture
def sources(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "helper.js").write_bytes(
        b"function helper(){\r target();\r}\r\rfunction target(){}\r"
    )
    (root / "caller.js").write_bytes(b"function caller(){\n return helper();\n}\n")
    (root / "other.js").write_bytes(b"function other(){}\n")
    return root


def extract(root, cache, **opts):
    return adapter.extract_boundary_ir(
        root,
        incremental=True,
        cache_dir=cache,
        created_at="2000-01-01T00:00:00Z",
        fail_fast=True,
        **opts,
    )


def legacy_v3_key(payload):
    """P06 key encoding, independent of the current cache field selection."""
    fields = [
        "path",
        "content_hash",
        "language",
        "grammar_version",
        "runtime_version",
        "tool_version",
        "schema_version",
        "resolution_mode",
        "fail_fast",
        "include_retrieval_metadata",
    ]
    if payload.get("semantic_schema_version") is not None:
        fields.extend(
            ("semantic_min_confidence", "semantic_resolvers", "semantic_schema_version")
        )
    fields.extend(
        field
        for field in (
            "call_resolution",
            "call_resolution_version",
            "call_resolution_symlink",
        )
        if field in payload
    )
    encoded = json.dumps(
        {field: payload[field] for field in fields},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "boundary:v3:" + hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize(
    "opts",
    [
        {},
        {"call_resolution": "structural"},
        {"call_resolution": "imports"},
        {"semantic_resolvers": ()},
    ],
    ids=["default", "structural", "imports", "semantic"],
)
def test_legacy_records_migrate_once(sources, tmp_path, opts):
    cache = tmp_path / "cache"
    # Seed v3 using the previous file identity and the parser's LF-only rows.
    with (
        patch.object(adapter, "_build_boundary_cache_key", legacy_v3_key),
        patch.object(
            adapter,
            "_cache_source_identity",
            side_effect=lambda path, lang: (
                adapter._content_hash(path.read_bytes()),
                False,
            ),
        ),
        patch.object(core, "_chunk_line_offsets", return_value=()),
        patch.object(
            symbol_graph,
            "_line_ending_offsets",
            side_effect=lambda src: [i for i, b in enumerate(src) if b == 10],
        ),
    ):
        legacy = extract(sources, cache, **opts)
    assert (
        next(
            n["span"]["start_line"] for n in legacy["nodes"] if n["symbol"] == "target"
        )
        == 1
    )
    before = load_cache_index(cache).records
    with patch.object(
        adapter, "_extract_file_cache_record", wraps=adapter._extract_file_cache_record
    ) as spy:
        upgraded = extract(sources, cache, **opts)
        assert sorted(c.args[0].name for c in spy.call_args_list) == [
            "caller.js",
            "helper.js",
        ]
        spy.reset_mock()
        assert extract(sources, cache, **opts) == upgraded
        spy.assert_not_called()
    after = load_cache_index(cache).records
    assert {p for p in before if before[p] != after[p]} == {"helper.js"}
    assert (
        next(
            n["span"]["start_line"]
            for n in upgraded["nodes"]
            if n["symbol"] == "target"
        )
        == 5
    )
    assert any(
        e["type"] == "calls"
        and e["location"]["start_line"] == 2
        and e["location"]["byte_start"]
        == (sources / "helper.js").read_bytes().index(b"target()")
        for e in upgraded["edges"]
    )
    assert upgraded == extract(sources, tmp_path / "fresh", **opts)


def test_name_identity_on_affected_file(sources, tmp_path):
    default = tmp_path / "default"
    explicit = tmp_path / "explicit"
    assert json.dumps(symbol_graph.extract_symbol_graph(sources)) == json.dumps(
        symbol_graph.extract_symbol_graph(sources, call_resolution="name")
    )
    assert json.dumps(extract(sources, default)) == json.dumps(
        extract(sources, explicit, call_resolution="name")
    )

    def files(root):
        return {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}

    assert files(default) == files(explicit)
    with patch.object(
        adapter, "_extract_file_cache_record", side_effect=AssertionError
    ):
        extract(sources, default, call_resolution="name")
        extract(sources, explicit)
