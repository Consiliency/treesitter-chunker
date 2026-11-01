"""Production pin sources and shared admission helpers (treesitter-chunker#362).

Covers the ADMITPIN contract as implemented by ADMIT SL-core-1: the
``chunker.trusted_artifacts.v1`` reader, the user-config pin file, the
``--trusted-artifacts`` option of the argparse ``grammar`` group, the
precedence rule, rule 3 (one-field records, no probe without a pin) and the
in-process verdict-reuse key. Native checks use a real BAML grammar compiled
from ``packages/baml-grammar/src``. Every test isolates ``HOME``,
``USERPROFILE``, ``APPDATA`` and ``XDG_CONFIG_HOME``.
"""

from __future__ import annotations

import json
import os
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from chunker._internal import grammar_management, native_admission
from chunker._internal import trusted_artifacts as pins_module
from chunker._internal.grammar_management import SmartGrammarManager
from chunker._internal.trusted_artifacts import (
    PIN_FILE_LIMIT,
    TRUSTED_ARTIFACTS_SCHEMA,
    copy_trusted_artifacts,
    load_user_config_pins,
    pin_provenance,
    read_trusted_artifacts,
    resolve_command_pins,
    user_config_pin_path,
)
from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from chunker.exceptions import ChunkerError, TrustedArtifactsError
from chunker.grammar.integrity import probe_native_grammar
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture

SUBCOMMANDS = [
    ["list"],
    ["info", "baml"],
    ["install", "baml", "https://invalid.invalid/repo.git"],
    ["update", "baml"],
    ["remove", "baml"],
    ["diagnose", "baml"],
    ["health"],
    ["validate"],
]


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


def _document(artifacts: dict[str, object]) -> str:
    return json.dumps({"schema": TRUSTED_ARTIFACTS_SCHEMA, "artifacts": artifacts})


def _pin_of(data: bytes) -> dict[str, str]:
    return {"sha256": sha256(data).hexdigest()}


@pytest.fixture(scope="module")
def baml_library(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("baml-fixture")
    return _compile_probe_fixture(directory, [SOURCE / "parser.c"])


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.delenv("CHUNKER_GRAMMAR_BUILD_DIR", raising=False)
    return home


def _write_config(text: str | bytes) -> Path:
    path = user_config_pin_path()
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the real ``get_grammar_tools`` factory at a private project tree."""
    root = tmp_path / "project"
    module_file = root / "chunker" / "cli" / "grammar_commands.py"
    build_dir = root / "chunker" / "data" / "grammars" / "build"
    build_dir.mkdir(parents=True)
    (root / "grammars").mkdir()
    monkeypatch.setattr(grammar_commands, "__file__", str(module_file))
    return build_dir


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def recording(path, language, *, provenance, **kwargs):
        calls.append(
            {
                "path": Path(path),
                "language": language,
                "provenance": provenance,
            }
        )
        return probe_native_grammar(path, language, provenance=provenance, **kwargs)

    monkeypatch.setattr(grammar_management, "probe_native_grammar", recording)
    return calls


def _grammar(monkeypatch, capsys, *argv: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["chunker", "grammar", *argv])
    code = main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- user-config pin file location -------------------------------------------


@pytest.mark.parametrize(
    ("platform_name", "expected_parts"),
    [
        ("linux", ("xdg", "treesitter-chunker", "trusted-artifacts.json")),
        (
            "darwin",
            (
                "Library",
                "Application Support",
                "treesitter-chunker",
                "trusted-artifacts.json",
            ),
        ),
        (
            "win32",
            ("AppData", "Roaming", "treesitter-chunker", "trusted-artifacts.json"),
        ),
    ],
)
def test_user_config_pin_path_per_platform(
    config_home, monkeypatch, platform_name, expected_parts
):
    monkeypatch.setattr(pins_module.sys, "platform", platform_name)
    path = user_config_pin_path()
    require(path is not None, "path resolved")
    require(path.parts[-len(expected_parts) :] == expected_parts, f"path {path}")
    require(str(path).startswith(str(config_home)), f"under isolated home {path}")


def test_user_config_pin_path_ignores_relative_base_directories(
    config_home, monkeypatch
):
    monkeypatch.setattr(pins_module.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/xdg")
    path = user_config_pin_path()
    require(
        path
        == Path.home() / ".config" / "treesitter-chunker" / "trusted-artifacts.json",
        f"relative XDG_CONFIG_HOME ignored {path}",
    )
    monkeypatch.setattr(pins_module.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "relative\\appdata")
    require(user_config_pin_path() is None, "relative APPDATA means no file")
    monkeypatch.delenv("APPDATA")
    require(user_config_pin_path() is None, "unset APPDATA means no file")


# --- reader --------------------------------------------------------------------


def test_reader_accepts_exact_schema_and_normalizes_hex(tmp_path):
    path = tmp_path / "pins.json"
    path.write_text(
        _document({"python": {"sha256": "AB" * 32}, "c-sharp_2": {"sha256": "0" * 64}}),
        encoding="utf-8",
    )
    require(
        read_trusted_artifacts(path)
        == {"python": {"sha256": "ab" * 32}, "c-sharp_2": {"sha256": "0" * 64}},
        "parsed pins",
    )
    path.write_text(_document({}), encoding="utf-8")
    require(read_trusted_artifacts(path) == {}, "empty artifacts is valid")


DEFECTS = {
    "malformed": (b"{not json", "not valid JSON"),
    "not_utf8": (b'{"schema": "\xff"}', "not valid UTF-8"),
    "duplicate_key": (
        f'{{"schema": "{TRUSTED_ARTIFACTS_SCHEMA}", "schema": "x", "artifacts": {{}}}}'.encode(),
        "duplicate key",
    ),
    "duplicate_language": (
        (
            f'{{"schema": "{TRUSTED_ARTIFACTS_SCHEMA}", "artifacts": '
            f'{{"a": {{"sha256": "{"0" * 64}"}}, "a": {{"sha256": "{"1" * 64}"}}}}}}'
        ).encode(),
        "duplicate key",
    ),
    "wrong_schema": (
        json.dumps(
            {"schema": "chunker.trusted_artifacts.v2", "artifacts": {}}
        ).encode(),
        '"schema" must be exactly',
    ),
    "extra_top_level": (
        json.dumps(
            {"schema": TRUSTED_ARTIFACTS_SCHEMA, "artifacts": {}, "trust_all": True}
        ).encode(),
        "top level must be an object",
    ),
    "artifacts_not_object": (
        json.dumps({"schema": TRUSTED_ARTIFACTS_SCHEMA, "artifacts": []}).encode(),
        '"artifacts" must be an object',
    ),
    "bad_language_key": (
        _document({"../python": {"sha256": "0" * 64}}).encode(),
        "invalid language key",
    ),
    "extra_record_key": (
        _document({"python": {"sha256": "0" * 64, "path": "/x"}}).encode(),
        'exactly "sha256"',
    ),
    "short_digest": (
        _document({"python": {"sha256": "0" * 63}}).encode(),
        "64 hex digits",
    ),
    "non_string_digest": (
        _document({"python": {"sha256": 7}}).encode(),
        "64 hex digits",
    ),
    "nan_constant": (
        f'{{"schema": "{TRUSTED_ARTIFACTS_SCHEMA}", "artifacts": NaN}}'.encode(),
        "not valid JSON",
    ),
}


@pytest.mark.parametrize("case", sorted(DEFECTS))
def test_reader_rejects_each_defect_whole_file(tmp_path, case):
    data, expected = DEFECTS[case]
    path = tmp_path / "pins.json"
    path.write_bytes(data)
    with pytest.raises(TrustedArtifactsError) as caught:
        read_trusted_artifacts(path)
    require(isinstance(caught.value, ChunkerError), "ChunkerError subclass")
    require(caught.value.path == str(path), f"names file {caught.value.path}")
    require(expected in caught.value.defect, f"{case}: {caught.value.defect}")
    require(str(path) in str(caught.value), "message names file")


def test_reader_rejects_oversized_directory_and_missing(tmp_path):
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (PIN_FILE_LIMIT + 1))
    with pytest.raises(TrustedArtifactsError, match="larger than"):
        read_trusted_artifacts(big)
    directory = tmp_path / "dir.json"
    directory.mkdir()
    with pytest.raises(TrustedArtifactsError):
        read_trusted_artifacts(directory)
    with pytest.raises(TrustedArtifactsError, match="file not found"):
        read_trusted_artifacts(tmp_path / "absent.json")


def test_config_file_inside_tool_written_directories_is_defective(
    config_home, tmp_path, monkeypatch
):
    document = _document({"baml": {"sha256": "0" * 64}})
    cache_root = config_home / ".cache" / "treesitter-chunker"
    cache_root.mkdir(parents=True)
    inside_cache = cache_root / "trusted-artifacts.json"
    inside_cache.write_text(document, encoding="utf-8")
    config = user_config_pin_path()
    assert config is not None
    config.parent.mkdir(parents=True)
    if os.name == "nt":
        pytest.skip("symlink creation needs privileges on Windows")
    config.symlink_to(inside_cache)
    with pytest.raises(TrustedArtifactsError, match="tool-written directory"):
        load_user_config_pins()

    config.unlink()
    build_override = tmp_path / "override-build"
    build_override.mkdir()
    (build_override / "pins.json").write_text(document, encoding="utf-8")
    config.symlink_to(build_override / "pins.json")
    monkeypatch.setenv("CHUNKER_GRAMMAR_BUILD_DIR", str(build_override))
    with pytest.raises(TrustedArtifactsError, match="tool-written directory"):
        load_user_config_pins()
    monkeypatch.delenv("CHUNKER_GRAMMAR_BUILD_DIR")
    require(load_user_config_pins() == {"baml": {"sha256": "0" * 64}}, "allowed")


def test_missing_config_file_supplies_no_pins(config_home):
    require(load_user_config_pins() is None, "absent file is not an error")
    require(resolve_command_pins(None) is None, "no source active")


def test_option_wins_over_config_and_is_never_merged(config_home, tmp_path):
    _write_config(_document({"baml": {"sha256": "1" * 64}}))
    option = tmp_path / "pins.json"
    option.write_text(_document({"python": {"sha256": "2" * 64}}), encoding="utf-8")
    require(
        resolve_command_pins(option) == {"python": {"sha256": "2" * 64}},
        "only the option file is active",
    )
    require(
        resolve_command_pins(None) == {"baml": {"sha256": "1" * 64}},
        "config applies without the option",
    )


# --- rule 2 and rule 3 -----------------------------------------------------------


def test_copy_and_one_field_record():
    source = {
        "baml": {"sha256": "a" * 64, "note": "extra"},
        "bad": "not a mapping",
        "nostr": {"sha256": 5},
    }
    copied = copy_trusted_artifacts(source)
    source["baml"]["sha256"] = "b" * 64
    require(copied["baml"]["sha256"] == "a" * 64, "copy isolated from caller")
    require("bad" not in copied, "non-Mapping record dropped")
    record = pin_provenance(copied, "baml")
    require(record == {"sha256": "a" * 64}, f"one-field record {record}")
    require(record is not copied["baml"], "fresh record, never the stored one")
    require(pin_provenance(copied, "nostr") is None, "non-str sha256")
    require(pin_provenance(copied, "absent") is None, "missing entry")
    require(pin_provenance(None, "baml") is None, "no pins")
    require(copy_trusted_artifacts("not a mapping") == {}, "non-Mapping argument")


def test_smart_manager_forwards_only_one_field_record(
    config_home, tmp_path, baml_library, probes
):
    build = tmp_path / "build"
    build.mkdir()
    (build / "baml.so").write_bytes(baml_library.read_bytes())
    pin = _pin_of(baml_library.read_bytes())
    manager = SmartGrammarManager(
        build,
        tmp_path / "sources",
        trusted_artifacts={"baml": {**pin, "extra": "ignored"}, "other": {"sha256": 3}},
    )
    health = manager.diagnose_grammar_issues("baml")
    require(health.status == "healthy", f"pinned fixture healthy {health!r}")
    require(len(probes) == 1, f"one probe {probes!r}")
    require(probes[0]["provenance"] == pin, f"record {probes[0]['provenance']!r}")
    (build / "other.so").write_bytes(b"other bytes")
    other = manager.diagnose_grammar_issues("other")
    require(other.validation_reason == "untrusted", f"non-str pin {other!r}")
    require(len(probes) == 1, "a non-str pin never calls the probe")


def test_constructor_never_reads_config_file(
    config_home, tmp_path, baml_library, probes
):
    _write_config(_document({"baml": _pin_of(baml_library.read_bytes())}))
    build = tmp_path / "build"
    build.mkdir()
    (build / "baml.so").write_bytes(baml_library.read_bytes())
    for pins in (None, {}):
        tools = UserGrammarTools(build, tmp_path / "sources", trusted_artifacts=pins)
        health = tools.manager.diagnose_grammar_issues("baml")
        require(health.validation_reason == "untrusted", f"{pins!r}: {health!r}")
    require(probes == [], "no probe without the constructor's own pin")


# --- argparse grammar group: EC-ADMIT-1 and the pin-source rules -------------------


def test_grammar_info_with_option_pins_exits_zero(
    config_home, project, baml_library, probes, monkeypatch, capsys, tmp_path
):
    (project / "baml.so").write_bytes(baml_library.read_bytes())
    option = tmp_path / "pins.json"
    option.write_text(
        _document({"baml": _pin_of(baml_library.read_bytes())}), encoding="utf-8"
    )
    for command in ("info", "diagnose"):
        code, out, err = _grammar(
            monkeypatch, capsys, "--trusted-artifacts", str(option), command, "baml"
        )
        require("Status: ✅ healthy" in out, f"{command}: {out!r}")
        require(code == 0, f"{command}: exit {code} {err!r}")
    require(
        probes and probes[0]["provenance"] == _pin_of(baml_library.read_bytes()),
        f"probe got the option's record {probes!r}",
    )


def test_grammar_info_without_pins_exits_one_untrusted(
    config_home, project, baml_library, probes, monkeypatch, capsys
):
    (project / "baml.so").write_bytes(baml_library.read_bytes())
    code, out, err = _grammar(monkeypatch, capsys, "info", "baml")
    require("Status: ⚠️ incompatible" in out, out)
    require("Native admission failed: untrusted" in out, out)
    require(code == 1, f"exit {code}")
    require(probes == [], "no probe without a pin")


def test_grammar_info_reads_user_config_pins(
    config_home, project, baml_library, monkeypatch, capsys
):
    (project / "baml.so").write_bytes(baml_library.read_bytes())
    _write_config(_document({"baml": _pin_of(baml_library.read_bytes())}))
    code, out, err = _grammar(monkeypatch, capsys, "info", "baml")
    require("Status: ✅ healthy" in out, f"config pins applied {out!r} {err!r}")
    require(code == 0, f"exit {code}")


def test_option_with_empty_artifacts_shuts_off_config_pins(
    config_home, project, baml_library, probes, monkeypatch, capsys, tmp_path
):
    (project / "baml.so").write_bytes(baml_library.read_bytes())
    _write_config(_document({"baml": _pin_of(baml_library.read_bytes())}))
    option = tmp_path / "empty.json"
    option.write_text(_document({}), encoding="utf-8")
    code, out, err = _grammar(
        monkeypatch, capsys, "--trusted-artifacts", str(option), "info", "baml"
    )
    require("Native admission failed: untrusted" in out, f"never merged {out!r}")
    require(code == 1, f"exit {code}")
    require(probes == [], "config pin not consulted")


@pytest.mark.parametrize("argv", SUBCOMMANDS, ids=lambda argv: argv[0])
def test_defective_config_exits_two_for_every_subcommand(
    config_home, project, probes, monkeypatch, capsys, argv
):
    (project / "baml.so").write_bytes(b"would be probed")
    config = _write_config("{broken")
    calls = []
    monkeypatch.setattr(
        grammar_commands,
        "get_grammar_tools",
        lambda *args, **kwargs: calls.append(args) or pytest.fail("tools built"),
    )
    code, out, err = _grammar(monkeypatch, capsys, *argv)
    require(code == 2, f"{argv}: exit {code}")
    require(str(config) in err and "not valid JSON" in err, f"{argv}: {err!r}")
    require(calls == [] and probes == [], "nothing discovered or probed")
    require((project / "baml.so").read_bytes() == b"would be probed", "untouched")


@pytest.mark.parametrize("case", ["missing", "defective"])
def test_defective_option_exits_two_before_any_probe(
    config_home, project, probes, monkeypatch, capsys, tmp_path, case
):
    (project / "baml.so").write_bytes(b"x")
    option = tmp_path / "pins.json"
    if case == "defective":
        option.write_text(_document({"baml": {"sha256": "short"}}), encoding="utf-8")
    code, out, err = _grammar(
        monkeypatch, capsys, "--trusted-artifacts", str(option), "info", "baml"
    )
    require(code == 2, f"exit {code}")
    require(str(option) in err, f"names file {err!r}")
    require(probes == [], "no probe")
    require("Status:" not in out, "no report")


def test_valid_option_ignores_defective_config(
    config_home, project, baml_library, monkeypatch, capsys, tmp_path
):
    (project / "baml.so").write_bytes(baml_library.read_bytes())
    _write_config("{broken")
    option = tmp_path / "pins.json"
    option.write_text(
        _document({"baml": _pin_of(baml_library.read_bytes())}), encoding="utf-8"
    )
    code, out, err = _grammar(
        monkeypatch, capsys, "--trusted-artifacts", str(option), "info", "baml"
    )
    require(code == 0 and "Status: ✅ healthy" in out, f"{code} {out!r} {err!r}")


# --- verdict reuse (in-process only, frozen key) -------------------------------------


def _counting_probe(calls: list[dict[str, object]]):
    def probe(path, language, **kwargs):
        calls.append({"path": Path(path), **kwargs})
        return probe_native_grammar(path, language, **kwargs)

    return probe


def test_verdict_reused_only_for_same_bytes_and_pin(tmp_path, baml_library):
    calls: list[dict[str, object]] = []
    candidate = tmp_path / "baml.so"
    data = baml_library.read_bytes()
    candidate.write_bytes(data)
    pins = {"baml": _pin_of(data)}
    first, _ = native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    second, _ = native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(first.supported and second.supported, f"{first} {second}")
    require(len(calls) == 1, f"second answered from this process {calls!r}")

    # Same-stat byte replacement: same size and mtime, different bytes.
    status = candidate.stat()
    replaced = bytearray(data)
    replaced[len(replaced) // 2] ^= 0xFF
    candidate.write_bytes(bytes(replaced))
    os.utime(candidate, ns=(status.st_atime_ns, status.st_mtime_ns))
    require(candidate.stat().st_size == status.st_size, "same size")
    third, _ = native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(third.reason == "integrity_mismatch", f"same-stat replacement {third}")

    # A changed pin record never reuses the verdict for the old pin.
    candidate.write_bytes(data)
    other_pin = {"baml": _pin_of(bytes(replaced))}
    fourth, _ = native_admission.admit_native_candidate(
        candidate, "baml", other_pin, probe=_counting_probe(calls)
    )
    require(not fourth.supported, f"pin change misses {fourth}")
    require(len(calls) == 1, f"no probe for mismatched bytes {calls!r}")


def test_verdict_misses_across_environment(tmp_path, baml_library, monkeypatch):
    calls: list[dict[str, object]] = []
    candidate = tmp_path / "baml.so"
    candidate.write_bytes(baml_library.read_bytes())
    pins = {"baml": _pin_of(baml_library.read_bytes())}
    native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    original = native_admission._environment()
    for field in ("python", "abi", "platform", "machine", "chunker", "tree_sitter"):
        changed = {**original, field: f"other-{field}"}
        monkeypatch.setattr(
            native_admission, "_environment", lambda changed=changed: changed
        )
        native_admission.admit_native_candidate(
            candidate, "baml", pins, probe=_counting_probe(calls)
        )
    changed = {**original, "validator_schema": original["validator_schema"] + 1}
    monkeypatch.setattr(native_admission, "_environment", lambda: changed)
    native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(len(calls) == 8, f"each environment change probes again: {len(calls)}")


def test_verdict_misses_across_inspector_and_probe_profile(tmp_path, baml_library):
    calls: list[dict[str, object]] = []
    candidate = tmp_path / "baml.so"
    candidate.write_bytes(baml_library.read_bytes())
    pins = {"baml": _pin_of(baml_library.read_bytes())}
    plain, metadata = native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(plain.supported and metadata is None, "probe-only ok")
    inspected, metadata = native_admission.admit_native_candidate(
        candidate,
        "baml",
        pins,
        inspector="test.v1",
        inspect_artifact=lambda snapshot: {"size": snapshot.stat().st_size},
        probe=_counting_probe(calls),
    )
    require(len(calls) == 2, "probe-only verdict never answers an inspector")
    require(metadata == {"size": candidate.stat().st_size}, f"metadata {metadata}")
    reused, reused_metadata = native_admission.admit_native_candidate(
        candidate,
        "baml",
        pins,
        inspector="test.v1",
        inspect_artifact=lambda snapshot: pytest.fail("reused"),
        probe=_counting_probe(calls),
    )
    require(reused_metadata == metadata and len(calls) == 2, "same inspector reuses")
    native_admission.admit_native_candidate(
        candidate,
        "baml",
        pins,
        inspector="other.v1",
        inspect_artifact=lambda snapshot: {},
        probe=_counting_probe(calls),
    )
    require(len(calls) == 3, "another inspector misses")
    for kwargs in ({"sample": b"model M {}"}, {"timeout": 9.0}):
        native_admission.admit_native_candidate(
            candidate, "baml", pins, probe=_counting_probe(calls), **kwargs
        )
        native_admission.admit_native_candidate(
            candidate, "baml", pins, probe=_counting_probe(calls), **kwargs
        )
    require(len(calls) == 7, f"non-default profiles never reuse or store {len(calls)}")
    native_admission.admit_native_candidate(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(len(calls) == 7, "default profile still reused")


def test_verdict_key_has_no_path_or_stat_fields():
    key_a = native_admission.verdict_key(
        language="baml",
        pin_sha256="A" * 64,
        content_sha256="a" * 64,
        level="probe",
        inspector="none",
    )
    key_b = native_admission.verdict_key(
        language="baml",
        pin_sha256="a" * 64,
        content_sha256="A" * 64,
        level="probe",
        inspector="none",
    )
    require(key_a == key_b, "digests compared lower-cased")
    require(
        key_a
        != native_admission.verdict_key(
            language="baml",
            pin_sha256="a" * 64,
            content_sha256="a" * 64,
            level="standard",
            inspector="none",
        ),
        "level is part of the key",
    )


# --- in-process copies ------------------------------------------------------------


def test_admitted_private_copy_loads_only_verified_copy(tmp_path, baml_library):
    calls: list[dict[str, object]] = []
    candidate = tmp_path / "baml.so"
    data = baml_library.read_bytes()
    candidate.write_bytes(data)
    pins = {"baml": _pin_of(data)}
    unpinned, none_copy = native_admission.admitted_private_copy(
        candidate, "baml", {}, probe=_counting_probe(calls)
    )
    require(unpinned.reason == "untrusted" and none_copy is None, "no pin, no copy")
    result, copy = native_admission.admitted_private_copy(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(result.supported and copy is not None, f"admitted {result}")
    require(copy != candidate and copy.read_bytes() == data, "verified private copy")
    require(copy.parent.name.startswith("chunker-admitted-"), f"prefix {copy}")
    require(calls[0]["path"] == copy, "the probe admitted the copy itself")
    again, same = native_admission.admitted_private_copy(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(again.supported and same == copy and len(calls) == 1, "one copy per pair")
    candidate.write_bytes(b"replaced bytes")
    replaced, no_copy = native_admission.admitted_private_copy(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(replaced.reason == "integrity_mismatch" and no_copy is None, "replaced")
    native_admission.forget_private_copy("baml", pins["baml"]["sha256"])
    candidate.write_bytes(data)
    fresh, fresh_copy = native_admission.admitted_private_copy(
        candidate, "baml", pins, probe=_counting_probe(calls)
    )
    require(
        fresh.supported and fresh_copy != copy, "load failure forces a new admission"
    )
    require(len(calls) == 2, f"probed again after forget {len(calls)}")


def test_hashing_and_pin_reading_are_byte_exact(tmp_path):
    """Windows text-mode reads would translate CRLF and stop at Ctrl-Z."""
    data = b"\x7fELF\r\n\x1a\r\r\n\x00" * 4096
    candidate = tmp_path / "binary.so"
    candidate.write_bytes(data)
    require(
        native_admission.hash_regular_file(candidate) == sha256(data).hexdigest(),
        "hash matches the file's exact bytes",
    )
    pins = tmp_path / "pins.json"
    pins.write_bytes(
        b'{"schema": "chunker.trusted_artifacts.v1",\r\n "artifacts": {"x": {"sha256": "'
        + b"a" * 64
        + b'"}}}\r\n'
    )
    require(read_trusted_artifacts(pins) == {"x": {"sha256": "a" * 64}}, "CRLF file")
