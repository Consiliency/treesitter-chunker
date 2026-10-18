import hashlib
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
    _record_filename,
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


def test_496_anchor_genuine_v1_cache_reparses_then_reuses_v3(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return sorted([])\n", encoding="utf-8")
    cache_dir = tmp_path / ".boundary-cache"
    baseline_cache = Path(__file__).parent / "fixtures" / "boundary_cache" / "v1_python"
    shutil.copytree(baseline_cache, cache_dir)
    raw_index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert raw_index["cache_version"] == "1"
    assert raw_index["schema_version"] == "2.0"
    baseline_key = raw_index["records"]["app.py"]
    baseline_record = cache_dir / _record_filename(baseline_key)
    assert baseline_record.exists()
    fresh = extract_boundary_ir(tmp_path, "python")

    from chunker.boundary import adapter

    recomputed: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path, *args, **kwargs):
        recomputed.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    cold = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == ["app.py"]
    assert baseline_record.exists()
    migrated_index = load_cache_index(cache_dir)
    assert migrated_index.records["app.py"].startswith("boundary:v3:")
    migrated_record = load_cache_record(cache_dir, migrated_index.records["app.py"])
    assert migrated_record is not None
    assert migrated_record.symbol_facts["symbol_lookup"]

    recomputed.clear()
    warm = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == []
    assert dumps_boundary_ir(fresh) == dumps_boundary_ir(cold)
    assert dumps_boundary_ir(cold) == dumps_boundary_ir(warm)


def test_496_same_schema_v2_cache_reparses_then_reuses_v3(tmp_path: Path, monkeypatch):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return sorted([])\n", encoding="utf-8")
    cache_dir = tmp_path / ".boundary-cache"
    fresh = extract_boundary_ir(tmp_path, "python")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)
    current_index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    current_key = current_index["records"][source.name]
    current_path = cache_dir / _record_filename(current_key)
    record = json.loads(current_path.read_text(encoding="utf-8"))
    old_key = current_key.replace("boundary:v3:", "boundary:v2:")
    record["cache_version"] = "2"
    record["cache_key"] = old_key
    old_path = cache_dir / _record_filename(old_key)
    old_path.write_text(json.dumps(record), encoding="utf-8")
    current_path.unlink()
    current_index["cache_version"] = "2"
    current_index["records"][source.name] = old_key
    (cache_dir / "index.json").write_text(json.dumps(current_index), encoding="utf-8")
    assert load_cache_index(cache_dir) == BoundaryCacheIndex()
    assert load_cache_record(cache_dir, old_key) is None

    from chunker.boundary import adapter

    recomputed: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path, *args, **kwargs):
        recomputed.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    migrated = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == [source.name]
    migrated_index = load_cache_index(cache_dir)
    migrated_key = migrated_index.records[source.name]
    assert migrated_key.startswith("boundary:v3:")
    migrated_record = load_cache_record(cache_dir, migrated_key)
    assert migrated_record is not None
    assert migrated_record.symbol_facts["call_facts"]

    recomputed.clear()
    warm = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == []
    assert dumps_boundary_ir(fresh) == dumps_boundary_ir(migrated)
    assert dumps_boundary_ir(migrated) == dumps_boundary_ir(warm)


@pytest.mark.parametrize("defect", ["missing", "location-type"])
def test_496_malformed_v3_facts_reparse_then_reuse_repaired_record(
    tmp_path: Path, monkeypatch, defect: str
):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return sorted([])\n", encoding="utf-8")
    cache_dir = tmp_path / ".boundary-cache"
    fresh = extract_boundary_ir(tmp_path, "python")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)
    index = load_cache_index(cache_dir)
    key = index.records[source.name]
    record_path = cache_dir / _record_filename(key)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert load_cache_record(cache_dir, key) is not None
    if defect == "missing":
        record["symbol_facts"].pop("call_facts")
    else:
        record["symbol_facts"]["call_facts"][0]["location"]["byte_start"] = "0"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert load_cache_record(cache_dir, key) is None

    from chunker.boundary import adapter

    recomputed: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path, *args, **kwargs):
        recomputed.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    repaired = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == [source.name]
    repaired_index = load_cache_index(cache_dir)
    repaired_record = load_cache_record(cache_dir, repaired_index.records[source.name])
    assert repaired_record is not None
    assert repaired_record.symbol_facts["call_facts"]

    recomputed.clear()
    warm = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    assert recomputed == []
    assert dumps_boundary_ir(fresh) == dumps_boundary_ir(repaired)
    assert dumps_boundary_ir(repaired) == dumps_boundary_ir(warm)


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
        from chunker._internal import registry as registry_module

        expected_digest = hashlib.sha256(custom.read_bytes()).hexdigest()
        with monkeypatch.context() as patch:
            loaded_paths = []
            real_cdll = registry_module.ctypes.CDLL

            def record_cdll(path, *args, **kwargs):
                loaded_paths.append(Path(path).resolve())
                return real_cdll(path, *args, **kwargs)

            patch.setattr(registry_module.ctypes, "CDLL", record_cdll)
            _set_parser_state(patch, custom.parent / f"languages{_LIB_EXT}")
            cold = extract_boundary_ir(
                tmp_path, language, incremental=True, cache_dir=cache_dir
            )
            warm = extract_boundary_ir(
                tmp_path, language, incremental=True, cache_dir=cache_dir
            )
            selected = parser._state.registry.get_language(language)
            assert not Parser(selected).parse(b"x = 1").root_node.has_error
            assert custom.resolve() in loaded_paths
            selected_source = parser._state.registry._selected_sources[language]
            assert selected_source == (
                selected,
                f"custom:sha256:{expected_digest}",
            )
        assert dumps_boundary_ir(cold) == dumps_boundary_ir(warm)
        custom_identity = _cache_payload(cache_dir, source.name)["grammar_version"]
        assert f":source=custom:sha256:{expected_digest}:" in custom_identity
        custom_identities.append(custom_identity)

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
@pytest.mark.parametrize("custom_source", ["individual", "combined"])
def test_492_known_version_incompatible_custom_fails_before_cache_identity(
    tmp_path, monkeypatch, language, previously_warm, custom_source
):
    from tree_sitter import Language

    from chunker._internal import language_pack
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
    if custom_source == "combined":
        combined = custom.with_name(f"languages{_LIB_EXT}")
        custom.rename(combined)
        custom = combined
    cache_dir = tmp_path.parent / f"{tmp_path.name}-custom-abi-cache"
    if previously_warm:
        with monkeypatch.context() as patch:
            _isolate_official_state(patch, tmp_path)
            seeded = extract_boundary_ir(
                tmp_path, None, incremental=True, cache_dir=cache_dir
            )
            assert all(item["status"] == "parsed" for item in seeded["files"])
    before = _cache_bytes(cache_dir)

    official_module = language_pack.import_module(f"tree_sitter_{language}")
    official_language = Language(official_module.language())
    official_source = (
        "\u017f = 1\n" if language == "python" else "const \u212a = 1;\n"
    ).encode("utf-8")
    assert (
        not registry_module.Parser(official_language)
        .parse(official_source)
        .root_node.has_error
    )

    with monkeypatch.context() as patch:
        state = _set_parser_state(
            patch,
            (
                custom
                if custom_source == "combined"
                else custom.parent / f"languages{_LIB_EXT}"
            ),
        )
        real_registry_parser = registry_module.Parser
        observed_versions = []
        rejected_custom = []

        real_provider = language_pack.get_language_from_pack

        def forbid_official_fallback(name):
            if name == language:
                pytest.fail(f"official provider used for rejected custom {name}")
            return real_provider(name)

        patch.setattr(language_pack, "get_language_from_pack", forbid_official_fallback)

        def reject_custom(grammar=None):
            if grammar is None:
                return real_registry_parser()
            loaded = state.registry._loaded_sources.get(language)
            if (
                loaded is not None
                and loaded[0] == grammar
                and loaded[1].startswith("custom:sha256:")
            ):
                entry = state.registry._languages.get(language)
                assert entry is not None
                observed_versions.append(entry[1].version)
                rejected_custom.append(grammar)
                raise ValueError("known-version custom ABI rejected")
            return real_registry_parser(grammar)

        patch.setattr(
            registry_module,
            "Parser",
            reject_custom,
        )
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
        assert "14" in observed_versions
        assert rejected_custom
        assert all(grammar != official_language for grammar in rejected_custom)
        assert language not in state.registry._selected_sources

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


@pytest.mark.parametrize("language", ["python", "javascript"])
@pytest.mark.parametrize("previously_warm", [False, True], ids=("cold", "warm"))
@pytest.mark.parametrize(
    "custom_source",
    ["combined", "individual-discovery", "individual-lazy"],
)
def test_492_null_custom_export_is_typed_and_preserves_mixed_cache(
    tmp_path, monkeypatch, language, previously_warm, custom_source
):
    from chunker import parser as parser_module
    from chunker._internal import language_pack
    from chunker._internal.registry import LanguageRegistry

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
    custom_path = _copy_pack_library(tmp_path, language, "null-custom")
    if custom_source == "combined":
        combined_path = custom_path.with_name(f"languages{_LIB_EXT}")
        custom_path.rename(combined_path)
        custom_path = combined_path
    else:
        combined_path = custom_path.with_name(f"missing{_LIB_EXT}")
    cache_dir = tmp_path.parent / f"{tmp_path.name}-null-custom-cache"
    if previously_warm:
        with monkeypatch.context() as patch:
            _isolate_official_state(patch, tmp_path)
            seeded = extract_boundary_ir(
                tmp_path, None, incremental=True, cache_dir=cache_dir
            )
            assert all(item["status"] == "parsed" for item in seeded["files"])
    before = _cache_bytes(cache_dir)

    with monkeypatch.context() as patch:
        state = _set_parser_state(patch, combined_path)
        real_construct = LanguageRegistry._language_from_ctypes_symbol
        observed_exports = []

        def return_null(self, lib, symbol_name, library_path, language_name):
            if library_path == custom_path and language_name == language:
                assert hasattr(lib, symbol_name)
                observed_exports.append(symbol_name)
                if custom_source == "individual-lazy" and len(observed_exports) == 1:
                    return real_construct(
                        self, lib, symbol_name, library_path, language_name
                    )
                raise ValueError(
                    f"{library_path} symbol {symbol_name} returned null for {language_name}"
                )
            return real_construct(self, lib, symbol_name, library_path, language_name)

        patch.setattr(LanguageRegistry, "_language_from_ctypes_symbol", return_null)
        real_provider = language_pack.get_language_from_pack

        def forbid_provider(name):
            if name == language:
                pytest.fail(f"official or pack provider used for null custom {name}")
            return real_provider(name)

        patch.setattr(language_pack, "get_language_from_pack", forbid_provider)

        def manager():
            pytest.fail("automatic grammar build used")

        patch.setattr(parser_module, "TreeSitterGrammarManager", manager)

        failed = extract_boundary_ir(
            tmp_path,
            None,
            incremental=True,
            cache_dir=cache_dir,
            fail_fast=False,
        )
        with pytest.raises(ParserInitError, match="returned null"):
            extract_boundary_ir(
                tmp_path,
                None,
                incremental=True,
                cache_dir=cache_dir,
                fail_fast=True,
            )
        expected_exports = 2 if custom_source == "individual-lazy" else 1
        assert observed_exports == [f"tree_sitter_{language}"] * expected_exports
        assert language not in state.registry._selected_sources

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
