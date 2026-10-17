import inspect
import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.cache import (
    BoundaryCacheIndex,
    build_boundary_cache_key,
    load_cache_index,
    load_cache_record,
    save_cache_index,
)
from chunker.exceptions import ParserInitError


_LIB_EXT = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")


def _cache_bytes(cache_dir: Path) -> dict[str, bytes]:
    return {
        path.relative_to(cache_dir).as_posix(): path.read_bytes()
        for path in sorted(cache_dir.rglob("*"))
        if path.is_file()
    }


def _cache_payload(cache_dir: Path, path: str) -> dict:
    index = load_cache_index(cache_dir)
    record = load_cache_record(cache_dir, index.records[path])
    assert record is not None
    return record.key_payload


def _copy_pack_library(tmp_path: Path, language: str, directory: str) -> Path:
    import tree_sitter_language_pack as pack

    pack.get_language(language)
    candidates = [
        path
        for path in Path(pack.cache_dir()).rglob(f"*tree_sitter_{language}*")
        if path.is_file() and path.suffix.lower() in {".so", ".dylib", ".dll"}
    ]
    assert len(candidates) == 1
    target_dir = tmp_path / directory
    target_dir.mkdir()
    target = target_dir / f"{language}{_LIB_EXT}"
    shutil.copy2(candidates[0], target)
    return target


def _set_parser_state(monkeypatch, library_path: Path):
    from chunker import parser

    state = parser._ParserState()
    state.default_library_path = library_path
    monkeypatch.setattr(parser, "_state", state)
    return state


def _isolate_official_state(monkeypatch, tmp_path: Path):
    from chunker._internal.registry import LanguageRegistry

    state = _set_parser_state(
        monkeypatch, tmp_path / "missing" / f"languages{_LIB_EXT}"
    )
    monkeypatch.setattr(LanguageRegistry, "_discover_symbols", lambda self: [])
    monkeypatch.setattr(
        LanguageRegistry,
        "_try_load_from_individual_library_safely",
        lambda self, name: None,
    )
    return state


def test_incremental_false_keeps_default_options(tmp_path: Path):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    default = extract_boundary_ir(tmp_path, "python")
    explicit = extract_boundary_ir(tmp_path, "python", incremental=False)

    assert default == explicit
    assert "incremental" not in default["run"]["options"]
    assert "cache_dir" not in default["run"]["options"]


def test_incremental_signature_exposes_new_keyword_only_parameters():
    params = inspect.signature(extract_boundary_ir).parameters

    assert params["incremental"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["cache_dir"].default is None
    assert params["force_rebuild"].default is False


def test_cold_and_warm_incremental_runs_are_byte_identical(tmp_path: Path):
    cache_dir = tmp_path / ".boundary-cache"
    (tmp_path / "helper.py").write_text(
        "def helper():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "service.py").write_text(
        """from helper import helper

def service():
    return helper()
""",
        encoding="utf-8",
    )

    cold = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    warm = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )

    assert dumps_boundary_ir(cold) == dumps_boundary_ir(warm)
    assert (cache_dir / "index.json").exists()


def test_incremental_warm_run_recomputes_changed_file_and_neighbors(
    tmp_path: Path, monkeypatch
):
    cache_dir = tmp_path / ".boundary-cache"
    helper = tmp_path / "helper.py"
    service = tmp_path / "service.py"
    unrelated = tmp_path / "unrelated.py"
    helper.write_text("def helper():\n    return 1\n", encoding="utf-8")
    service.write_text(
        """from helper import helper

def service():
    return helper()
""",
        encoding="utf-8",
    )
    unrelated.write_text("def other():\n    return 3\n", encoding="utf-8")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    from chunker.boundary import adapter

    recomputed: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path, *args, **kwargs):
        recomputed.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    helper.write_text("def helper():\n    return 2\n", encoding="utf-8")

    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    assert recomputed == ["helper.py", "service.py"]


def test_force_rebuild_refreshes_valid_cache_records(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / ".boundary-cache"
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    from chunker.boundary import adapter

    calls = 0
    original = adapter._extract_file_cache_record

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    extract_boundary_ir(
        tmp_path,
        "python",
        incremental=True,
        cache_dir=cache_dir,
        force_rebuild=True,
    )

    assert calls == 1


def test_incremental_fail_fast_parser_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "chunk_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
    )

    with pytest.raises(RuntimeError, match="parse boom"):
        extract_boundary_ir(tmp_path, "python", incremental=True, fail_fast=True)


@pytest.mark.parametrize("failing_operation", ["chunk_file", "_node_record"])
def test_transient_extraction_error_is_retried_without_source_change(
    tmp_path, monkeypatch, failing_operation
):
    from chunker.boundary import adapter

    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    cache_dir = tmp_path / ".boundary-cache"
    with monkeypatch.context() as patch:
        patch.setattr(
            adapter,
            failing_operation,
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("temporary extraction failure")
            ),
        )
        failed = extract_boundary_ir(
            tmp_path, "python", incremental=True, cache_dir=cache_dir, fail_fast=False
        )
    recovered = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir, fail_fast=False
    )
    assert not failed["nodes"]
    assert recovered["nodes"]


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_492_prefixed_cache_record_misses_and_reparses(tmp_path, monkeypatch, language):
    from chunker.boundary import adapter
    from chunker.boundary.cache import _record_filename

    suffix = "py" if language == "python" else "js"
    source = tmp_path / f"app.{suffix}"
    source.write_text(
        (
            "def ok():\n    return 1\n"
            if language == "python"
            else "function ok() { return 1; }\n"
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / ".boundary-cache"
    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        extract_boundary_ir(tmp_path, language, incremental=True, cache_dir=cache_dir)

    index = load_cache_index(cache_dir)
    current_key = index.records[source.name]
    current = load_cache_record(cache_dir, current_key)
    assert current is not None
    old_payload = dict(current.key_payload)
    old_payload["grammar_version"] = old_payload["grammar_version"].replace(
        f"source=official:tree-sitter-{language}@0.25.0:",
        "",
    )
    old_key = build_boundary_cache_key(old_payload)
    old_json = current.to_json()
    old_json["cache_key"] = old_key
    old_json["key_payload"] = old_payload
    old_path = cache_dir / _record_filename(old_key)
    old_path.write_text(
        json.dumps(old_json, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (cache_dir / _record_filename(current_key)).unlink()
    save_cache_index(
        cache_dir,
        BoundaryCacheIndex(
            records={source.name: old_key},
            content_hashes={source.name: current.content_hash},
        ),
    )

    recomputed = []
    original = adapter._extract_file_cache_record

    def spy(*args, **kwargs):
        recomputed.append(args[0].name)
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        repaired = extract_boundary_ir(
            tmp_path, language, incremental=True, cache_dir=cache_dir
        )

    assert recomputed == [source.name]
    assert repaired["files"][0]["status"] == "parsed"
    assert _cache_payload(cache_dir, source.name)["grammar_version"].startswith(
        f"tree-sitter-{language}:source=official:tree-sitter-{language}@0.25.0:"
    )


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_492_incremental_tracks_actual_official_and_custom_sources(
    tmp_path, monkeypatch, language
):
    from tree_sitter import Parser

    from chunker import parser
    from chunker.boundary import adapter

    suffix = "py" if language == "python" else "js"
    source = tmp_path / f"app.{suffix}"
    source.write_text(
        (
            "def ok():\n    return 1\n"
            if language == "python"
            else "function ok() { return 1; }\n"
        ),
        encoding="utf-8",
    )
    first_custom = _copy_pack_library(tmp_path, language, "custom-one")
    second_custom = _copy_pack_library(tmp_path, language, "custom-two")
    second_custom.write_bytes(second_custom.read_bytes() + b"unicode-492-distinct")
    cache_dir = tmp_path / "cache"
    recomputed = []
    original = adapter._extract_file_cache_record

    def spy(*args, **kwargs):
        recomputed.append(args[0].name)
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)

    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        official = extract_boundary_ir(
            tmp_path, language, incremental=True, cache_dir=cache_dir
        )
        official_warm = extract_boundary_ir(
            tmp_path, language, incremental=True, cache_dir=cache_dir
        )
        assert (
            not Parser(parser._state.registry.get_language(language))
            .parse(b"x = 1")
            .root_node.has_error
        )
    assert dumps_boundary_ir(official) == dumps_boundary_ir(official_warm)
    assert len(recomputed) == 1
    official_identity = _cache_payload(cache_dir, source.name)["grammar_version"]

    custom_identities = []
    for custom in (first_custom, second_custom):
        with monkeypatch.context() as patch:
            _set_parser_state(patch, custom.parent / f"languages{_LIB_EXT}")
            cold = extract_boundary_ir(
                tmp_path, language, incremental=True, cache_dir=cache_dir
            )
            warm = extract_boundary_ir(
                tmp_path, language, incremental=True, cache_dir=cache_dir
            )
            selected = parser._state.registry.get_language(language)
            assert not Parser(selected).parse(b"x = 1").root_node.has_error
        assert dumps_boundary_ir(cold) == dumps_boundary_ir(warm)
        custom_identities.append(
            _cache_payload(cache_dir, source.name)["grammar_version"]
        )

    assert len(recomputed) == 3
    assert official_identity != custom_identities[0]
    assert custom_identities[0] != custom_identities[1]
    assert all(":source=custom:sha256:" in item for item in custom_identities)

    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        restored = extract_boundary_ir(
            tmp_path, language, incremental=True, cache_dir=cache_dir
        )
        restored_warm = extract_boundary_ir(
            tmp_path, language, incremental=True, cache_dir=cache_dir
        )
    assert dumps_boundary_ir(restored) == dumps_boundary_ir(restored_warm)
    assert len(recomputed) == 4
    assert (
        _cache_payload(cache_dir, source.name)["grammar_version"] == official_identity
    )


def _inject_official_failure(monkeypatch, language: str, failure: str) -> None:
    import tree_sitter

    from chunker._internal import language_pack

    real_module = language_pack.import_module(f"tree_sitter_{language}")
    if failure == "module":
        injected = ImportError("missing official module")
    elif failure == "native":
        injected = OSError("official native load failed")
    elif failure == "capsule":
        injected = types.SimpleNamespace(language=object)
    else:
        injected = real_module
        monkeypatch.setattr(
            tree_sitter,
            "Parser",
            lambda language: (_ for _ in ()).throw(
                ValueError("official grammar ABI rejected")
            ),
        )
    if isinstance(injected, Exception):
        monkeypatch.setattr(
            language_pack,
            "import_module",
            lambda name: (_ for _ in ()).throw(injected),
        )
    else:
        monkeypatch.setattr(language_pack, "import_module", lambda name: injected)


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("failure", ["module", "native", "capsule", "abi"])
@pytest.mark.parametrize("previously_warm", [False, True], ids=("cold", "warm"))
def test_492_provider_failure_preserves_cache_and_mixed_file_continuation(
    tmp_path, monkeypatch, language, failure, previously_warm
):
    suffix = "py" if language == "python" else "js"
    affected = tmp_path / f"bad.{suffix}"
    affected.write_text(
        (
            "def bad():\n    return 1\n"
            if language == "python"
            else "function bad() { return 1; }\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "ok.go").write_text(
        "package main\nfunc ok() int { return 1 }\n", encoding="utf-8"
    )
    cache_dir = tmp_path.parent / f"{tmp_path.name}-boundary-cache"
    if previously_warm:
        with monkeypatch.context() as patch:
            _isolate_official_state(patch, tmp_path)
            seeded = extract_boundary_ir(
                tmp_path, None, incremental=True, cache_dir=cache_dir
            )
            assert all(item["status"] == "parsed" for item in seeded["files"])
    before = _cache_bytes(cache_dir)

    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        _inject_official_failure(patch, language, failure)
        failed = extract_boundary_ir(
            tmp_path,
            None,
            incremental=True,
            cache_dir=cache_dir,
            fail_fast=False,
        )
        with pytest.raises(ParserInitError, match=f"tree-sitter-{language}==0.25.0"):
            extract_boundary_ir(
                tmp_path,
                None,
                incremental=True,
                cache_dir=cache_dir,
                fail_fast=True,
            )

    files = {item["path"]: item for item in failed["files"]}
    assert files[affected.name]["status"] == "error"
    assert files["ok.go"]["status"] == "parsed"
    assert not [node for node in failed["nodes"] if node["path"] == affected.name]
    assert [node for node in failed["nodes"] if node["path"] == "ok.go"]
    assert any(
        item["code"] == "boundary.parse_error" and item["path"] == affected.name
        for item in failed["diagnostics"]
    )
    assert _cache_bytes(cache_dir) == before

    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        recovered = extract_boundary_ir(
            tmp_path, None, incremental=True, cache_dir=cache_dir
        )
        stable = _cache_bytes(cache_dir)
        recovered_warm = extract_boundary_ir(
            tmp_path, None, incremental=True, cache_dir=cache_dir
        )
    assert all(item["status"] == "parsed" for item in recovered["files"])
    assert dumps_boundary_ir(recovered) == dumps_boundary_ir(recovered_warm)
    assert _cache_bytes(cache_dir) == stable


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("previously_warm", [False, True], ids=("cold", "warm"))
def test_492_known_version_incompatible_custom_fails_before_cache_identity(
    tmp_path, monkeypatch, language, previously_warm
):
    from chunker import core
    from chunker._internal import registry as registry_module

    suffix = "py" if language == "python" else "js"
    affected = tmp_path / f"bad.{suffix}"
    affected.write_text(
        (
            "def bad():\n    return 1\n"
            if language == "python"
            else "function bad() { return 1; }\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "ok.go").write_text(
        "package main\nfunc ok() int { return 1 }\n", encoding="utf-8"
    )
    custom = _copy_pack_library(tmp_path, language, "custom-incompatible")
    cache_dir = tmp_path.parent / f"{tmp_path.name}-custom-abi-cache"
    if previously_warm:
        with monkeypatch.context() as patch:
            _isolate_official_state(patch, tmp_path)
            seeded = extract_boundary_ir(
                tmp_path, None, incremental=True, cache_dir=cache_dir
            )
            assert all(item["status"] == "parsed" for item in seeded["files"])
    before = _cache_bytes(cache_dir)

    with monkeypatch.context() as patch:
        state = _set_parser_state(patch, custom.parent / f"languages{_LIB_EXT}")
        state.initialize()
        metadata = state.registry.get_metadata(language)
        assert metadata.version != "unknown"
        assert metadata.capabilities["grammar_source"].startswith("custom:sha256:")
        selected = state.registry.get_language(language)
        real_get_parser = core.get_parser
        patch.setattr(
            registry_module,
            "Parser",
            lambda grammar: (_ for _ in ()).throw(
                ValueError("known-version custom ABI rejected")
            ),
        )

        def reject_selected(name, *args, **kwargs):
            if name == language:
                raise ParserInitError(language, "known-version custom ABI rejected")
            return real_get_parser(name, *args, **kwargs)

        patch.setattr(core, "get_parser", reject_selected)
        assert selected is state.registry.get_language(language)
        failed = extract_boundary_ir(
            tmp_path,
            None,
            incremental=True,
            cache_dir=cache_dir,
            fail_fast=False,
        )
        with pytest.raises(ParserInitError, match="known-version custom ABI rejected"):
            extract_boundary_ir(
                tmp_path,
                None,
                incremental=True,
                cache_dir=cache_dir,
                fail_fast=True,
            )

    files = {item["path"]: item for item in failed["files"]}
    assert files[affected.name]["status"] == "error"
    assert files["ok.go"]["status"] == "parsed"
    assert not [node for node in failed["nodes"] if node["path"] == affected.name]
    assert [node for node in failed["nodes"] if node["path"] == "ok.go"]
    assert _cache_bytes(cache_dir) == before

    with monkeypatch.context() as patch:
        _isolate_official_state(patch, tmp_path)
        recovered = extract_boundary_ir(
            tmp_path, None, incremental=True, cache_dir=cache_dir
        )
        stable = _cache_bytes(cache_dir)
        recovered_warm = extract_boundary_ir(
            tmp_path, None, incremental=True, cache_dir=cache_dir
        )
    assert all(item["status"] == "parsed" for item in recovered["files"])
    assert dumps_boundary_ir(recovered) == dumps_boundary_ir(recovered_warm)
    assert _cache_bytes(cache_dir) == stable
