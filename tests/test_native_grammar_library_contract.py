"""Legacy grammar tools select, enumerate and remove native-suffix libraries.

Selection is name-only: ``<language><native>`` wins whenever that entry exists,
else the legacy ``<language>.so`` is used. Admission still requires the caller's
pin. "Simulated" cases substitute ``_platform_library_suffix``; they never patch
``sys.platform`` or ``platform.system``.
"""

import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("native_policy_environment")

from tests.native_policy import run_isolated_baml_parse

from chunker._internal import grammar_management, user_grammar_tools
from chunker._internal.grammar_management import (
    SmartGrammarManager,
    _platform_library_suffix,
)
from chunker._internal.user_grammar_tools import UserGrammarTools
from chunker.cli import grammar_commands
from chunker.cli.__main__ import main
from tests.test_compiled_grammar_analysis_contract import (
    FIXTURE,
    SOURCE,
    _compile_probe_fixture,
    trusted_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
ACTUAL_SUFFIX = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
REPO_URL = "https://github.com/Consiliency/native-fixture.git"
SENTINEL_SOURCE = """
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#endif
static void enter(void) {
    const char *path = getenv("CHUNKER_TEST_NATIVE_SENTINEL");
    FILE *marker;
    if (!path) return;
    marker = fopen(path, "wb");
    if (marker) { fputs("entered", marker); fclose(marker); }
}
#ifdef _WIN32
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) enter();
    return TRUE;
}
#else
__attribute__((constructor)) static void start(void) { enter(); }
#endif
"""


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def test_require_is_active_under_current_optimization():
    with pytest.raises(AssertionError, match="^live-oracle$"):
        require(False, "live-oracle")


@pytest.fixture(scope="module")
def baml_bytes(tmp_path_factory) -> bytes:
    library = _compile_probe_fixture(
        tmp_path_factory.mktemp("baml-native"), [SOURCE / "parser.c"]
    )
    require(library.is_file(), "compiled BAML fixture exists")
    data = library.read_bytes()
    require(data, "compiled BAML fixture is nonempty")
    return data


@pytest.fixture(scope="module")
def sentinel_bytes(tmp_path_factory) -> bytes:
    directory = tmp_path_factory.mktemp("sentinel-native")
    code = directory / "sentinel.c"
    code.write_text(SENTINEL_SOURCE, encoding="utf-8")
    library = _compile_probe_fixture(directory, [code])
    require(library.is_file(), "compiled sentinel fixture exists")
    return library.read_bytes()


def _simulate(monkeypatch, suffix):
    if suffix != "actual":
        monkeypatch.setattr(
            grammar_management,
            "_platform_library_suffix",
            lambda platform=None: suffix,
        )
        return suffix
    return ACTUAL_SUFFIX


def _workspace(tmp_path):
    build = tmp_path / "build"
    sources = tmp_path / "sources"
    build.mkdir()
    sources.mkdir()
    return build, sources


def _pin(data: bytes) -> dict[str, str]:
    return {"sha256": sha256(data).hexdigest()}


def _record_probes(monkeypatch):
    calls = []
    original = grammar_management.probe_native_grammar

    def recording(path, language, **kwargs):
        calls.append(Path(path))
        return original(path, language, **kwargs)

    monkeypatch.setattr(grammar_management, "probe_native_grammar", recording)
    return calls


def _isolated_parse(library: Path) -> None:
    completed = run_isolated_baml_parse(ROOT, library, FIXTURE, timeout=60)
    require(
        completed.returncode == 0,
        f"isolated BAML parse of {library}: {completed.returncode} "
        f"{completed.stderr.decode(errors='replace')}",
    )


def _run_cli(monkeypatch, capsys, argv, tools):
    monkeypatch.setattr(grammar_commands, "get_grammar_tools", lambda *_args: tools)
    monkeypatch.setattr(sys, "argv", ["chunker", *argv])
    code = main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize(
    ("platform", "suffix"),
    [
        ("linux", ".so"),
        ("darwin", ".dylib"),
        ("win32", ".dll"),
        ("cygwin", ".so"),
        ("freebsd14", ".so"),
    ],
)
def test_platform_suffix_mapping(tmp_path, platform, suffix):
    require(_platform_library_suffix(platform) == suffix, f"{platform} -> {suffix}")
    require(_platform_library_suffix() == ACTUAL_SUFFIX, "unsimulated suffix")
    manager = SmartGrammarManager(tmp_path, tmp_path / "sources")
    require(manager.library_suffix == ACTUAL_SUFFIX, "manager suffix")
    require(
        manager._library_candidates("baml")
        == (tmp_path / f"baml{ACTUAL_SUFFIX}", tmp_path / "baml.so"),
        "exact-language candidates",
    )


@pytest.mark.parametrize("suffix", ["actual", ".dll", ".dylib", ".so"])
def test_native_library_diagnosed_with_approved_pin(
    tmp_path, monkeypatch, baml_bytes, suffix
):
    suffix = _simulate(monkeypatch, suffix)
    build, sources = _workspace(tmp_path)
    library = build / f"baml{suffix}"
    library.write_bytes(baml_bytes)
    _isolated_parse(library)
    probes = _record_probes(monkeypatch)
    pins = trusted_artifacts(library)
    pin = pins["baml"]
    require(pin == _pin(baml_bytes), "test pin binds compiled fixture bytes")
    manager = SmartGrammarManager(build, sources, trusted_artifacts=pins)
    require(manager.library_suffix == suffix, "simulated suffix selected")
    health = manager.diagnose_grammar_issues("baml")
    require(probes == [library.absolute()], f"NATIVE_PROBE_PATH {probes!r}")
    require(health.status == "healthy", f"healthy {health!r}")
    require(health.validation_reason == "ok", "reason ok")
    require(health.artifact_sha256 == pin["sha256"], "accepted digest is the pin")
    require(health.file_size == len(baml_bytes), "file size from snapshot")
    require(
        manager.get_grammar_compatibility("baml").compilation_date is None,
        "compilation date stays unknown",
    )

    unpinned = SmartGrammarManager(build, sources)
    rejected = unpinned.diagnose_grammar_issues("baml")
    require(rejected.status == "incompatible", f"unpinned {rejected!r}")
    require(rejected.validation_reason == "untrusted", "unpinned untrusted")
    require(rejected.artifact_sha256 is None, "no digest without approval")
    require(unpinned.trusted_artifacts == {}, "no self-pin")
    require(probes[-1] == library.absolute(), "unpinned probes native")
    require(library.read_bytes() == baml_bytes, "fixture unchanged")


NATIVE_FAILURES = {
    "empty": ("corrupted", {"empty"}),
    "mismatch": ("incompatible", {"integrity_mismatch"}),
    "directory": ("incompatible", {"untrusted", "child_failed"}),
    "dangling_symlink": ("missing", {"missing"}),
}


@pytest.mark.parametrize("state", sorted(NATIVE_FAILURES))
def test_failed_native_never_falls_back_to_valid_legacy(
    tmp_path, monkeypatch, baml_bytes, state
):
    if state == "dangling_symlink" and os.name == "nt":
        pytest.skip("dangling symlink priority is a POSIX directory-entry case")
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    legacy = build / "baml.so"
    legacy.write_bytes(baml_bytes)
    native = build / "baml.dll"
    if state == "empty":
        native.write_bytes(b"")
    elif state == "mismatch":
        native.write_bytes(b"different nonempty native bytes")
    elif state == "directory":
        native.mkdir()
    else:
        native.symlink_to(build / "absent-target.dll")
    require(os.path.lexists(native), "native entry exists")
    probes = _record_probes(monkeypatch)
    manager = SmartGrammarManager(
        build, sources, trusted_artifacts={"baml": _pin(baml_bytes)}
    )
    health = manager.diagnose_grammar_issues("baml")
    expected_status, reasons = NATIVE_FAILURES[state]
    # A nonempty regular file whose digest differs from the pin is reported
    # integrity_mismatch before any probe (verdict-reuse lookup order).
    expected_probes = [] if state == "mismatch" else [native.absolute()]
    require(probes == expected_probes, f"NATIVE_ONLY_PROBED {probes!r}")
    require(health.status != "healthy", "native failure never rescued")
    require(health.status == expected_status, f"{state}: {health.status}")
    require(health.validation_reason in reasons, f"{state}: {health!r}")
    require(legacy.read_bytes() == baml_bytes, "legacy unchanged")


def test_legacy_so_used_only_when_native_absent(tmp_path, monkeypatch, baml_bytes):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    legacy = build / "baml.so"
    legacy.write_bytes(baml_bytes)
    probes = _record_probes(monkeypatch)
    manager = SmartGrammarManager(
        build, sources, trusted_artifacts={"baml": _pin(baml_bytes)}
    )
    health = manager.diagnose_grammar_issues("baml")
    require(probes == [legacy.absolute()], f"LEGACY_PROBED {probes!r}")
    require(health.status == "healthy", f"legacy fallback {health!r}")
    require(
        not any("takes priority" in item for item in health.recommendations),
        "no shadow note without native",
    )


def test_native_priority_over_differing_legacy(tmp_path, monkeypatch, baml_bytes):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    native = build / "baml.dll"
    legacy = build / "baml.so"
    native.write_bytes(baml_bytes)
    legacy.write_bytes(b"different legacy bytes")
    probes = _record_probes(monkeypatch)
    manager = SmartGrammarManager(
        build, sources, trusted_artifacts={"baml": _pin(baml_bytes)}
    )
    health = manager.diagnose_grammar_issues("baml")
    require(probes == [native.absolute()], f"native probed {probes!r}")
    require(health.status == "healthy", f"native healthy {health!r}")
    shadow = (
        f"Legacy library {legacy} is ignored because native {native} takes priority"
    )
    require(shadow in health.recommendations, f"shadow note {health.recommendations!r}")

    manager.trusted_artifacts = {"baml": _pin(legacy.read_bytes())}
    mismatch = manager.diagnose_grammar_issues("baml")
    require(probes[-1] == native.absolute(), "native probed again")
    require(
        mismatch.validation_reason == "integrity_mismatch",
        f"legacy pin proves native probed {mismatch!r}",
    )


def test_enumeration_counts_languages_once_and_keeps_unrelated_untrusted(
    tmp_path, monkeypatch, baml_bytes
):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    (build / "baml.dll").write_bytes(baml_bytes)
    (build / "baml.so").write_bytes(b"garbage legacy")
    (build / "helper.dll").write_bytes(baml_bytes)
    (build / "notes.txt").write_text("not a grammar", encoding="utf-8")
    (build / "baml.dylib").write_bytes(baml_bytes)
    pins = {"baml": _pin(baml_bytes)}
    tools = UserGrammarTools(build, sources, trusted_artifacts=pins)
    listed = tools.list_installed_grammars()
    require(listed["total_grammars"] == 2, f"LANGUAGE_COUNT {listed['total_grammars']}")
    require(set(listed["grammars"]) == {"baml", "helper"}, f"rows {listed!r}")
    require(listed["healthy_grammars"] == 1, "one healthy")
    require(listed["problematic_grammars"] == 1, "one problematic")
    require(listed["grammars"]["baml"]["status"] == "healthy", "baml healthy")
    helper = listed["grammars"]["helper"]
    require(helper["validation_reason"] == "untrusted", f"helper {helper!r}")
    require(helper["artifact_sha256"] is None, "helper not admitted")
    require(helper["compilation_date"] is None, "no invented date")
    validated = tools.manager.validate_all_grammars()
    require(set(validated) == {"baml", "helper"}, f"validate keys {validated!r}")
    require(tools.manager.trusted_artifacts == pins, "no self-pin")


def test_enumeration_counts_legacy_so_languages(tmp_path):
    build, sources = _workspace(tmp_path)
    (build / "baml.so").write_bytes(b"baml bytes")
    (build / "helper.so").write_bytes(b"helper bytes")
    listed = UserGrammarTools(build, sources).list_installed_grammars()
    require(listed["total_grammars"] == 2, f"legacy count {listed!r}")
    require(set(listed["grammars"]) == {"baml", "helper"}, "legacy rows")


INVALID_ENUMERATED = ["..so", ".so", "a:b.so", "a\\b.so"]


@pytest.mark.skipif(os.name == "nt", reason="invalid fixture names are POSIX names")
def test_enumeration_omits_invalid_language_components(tmp_path, monkeypatch, capsys):
    build, sources = _workspace(tmp_path)
    (build / "baml.so").write_bytes(b"unpinned baml bytes")
    invalid = {}
    for name in INVALID_ENUMERATED:
        (build / name).write_bytes(f"invalid entry {name}".encode())
        invalid[name] = (build / name).read_bytes()
    probes = _record_probes(monkeypatch)
    tools = UserGrammarTools(build, sources)
    try:
        validated = tools.manager.validate_all_grammars()
        listed = tools.list_installed_grammars()
        code, out, err = _run_cli(monkeypatch, capsys, ["grammar", "list"], tools)
    except Exception as error:
        raise AssertionError(f"NATIVE_ENUM_COMPONENT raised {error!r}") from error
    require(
        list(validated) == ["baml"], f"NATIVE_ENUM_COMPONENT validate {validated!r}"
    )
    require(listed["total_grammars"] == 1, f"NATIVE_ENUM_COMPONENT count {listed!r}")
    require(list(listed["grammars"]) == ["baml"], "NATIVE_ENUM_COMPONENT rows")
    # Rule 3: the unpinned candidate is untrusted without calling the probe.
    require(probes == [], f"NATIVE_ENUM_COMPONENT probes {probes!r}")
    require(code == 0, f"NATIVE_ENUM_COMPONENT list exit {code!r} {err!r}")
    require("baml: incompatible" in out, "NATIVE_ENUM_COMPONENT baml row")
    require("Total grammars: 1" in out, "NATIVE_ENUM_COMPONENT public count")
    for name, data in invalid.items():
        require((build / name).read_bytes() == data, f"{name} unchanged")
    with pytest.raises(ValueError):
        tools.manager.diagnose_grammar_issues(".")


def test_remove_deletes_only_requested_language_pair(tmp_path, monkeypatch):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    removed = ["baml.dll", "baml.so"]
    kept = ["helper.dll", "bamlx.dll", "baml.dylib"]
    for name in removed + kept:
        (build / name).write_bytes(name.encode())
    (sources / "tree-sitter-baml").mkdir()
    (sources / "tree-sitter-helper").mkdir()
    tools = UserGrammarTools(build, sources)
    result = tools.remove_grammar("baml")
    require(result["status"] == "success", f"remove {result!r}")
    for name in removed:
        require(not os.path.lexists(build / name), f"REMOVED_PAIR {name} removed")
        require(
            f"Removed compiled grammar library: {name}" in result["steps_completed"],
            f"{name} step",
        )
    for name in kept:
        require(
            os.path.lexists(build / name)
            and (build / name).read_bytes() == name.encode(),
            f"REMOVE_KEPT {name}",
        )
    require(
        result["steps_completed"].count("Removed compiled grammar library") == 1,
        "generic step once",
    )
    require(not (sources / "tree-sitter-baml").exists(), "source removed")
    require((sources / "tree-sitter-helper").is_dir(), "other source kept")
    listed = tools.list_installed_grammars()
    require(set(listed["grammars"]) == {"helper", "bamlx"}, f"after {listed!r}")


@pytest.mark.skipif(os.name == "nt", reason="dangling symlink entry is POSIX-only")
def test_remove_deletes_dangling_native_entry(tmp_path, monkeypatch):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    target = tmp_path / "absent-target.dll"
    (build / "baml.dll").symlink_to(target)
    (build / "baml.so").write_bytes(b"legacy")
    result = UserGrammarTools(build, sources).remove_grammar("baml")
    require(result["status"] == "success", f"remove {result!r}")
    require(not os.path.lexists(build / "baml.dll"), "dangling native removed")
    require(not os.path.lexists(build / "baml.so"), "legacy removed")
    require(not os.path.lexists(target), "target never created")


@pytest.mark.parametrize("failing", ["native", "legacy"])
def test_remove_partial_failure_is_reported(tmp_path, monkeypatch, failing):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    native = build / "baml.dll"
    legacy = build / "baml.so"
    native.write_bytes(b"native")
    legacy.write_bytes(b"legacy")
    source = sources / "tree-sitter-baml"
    source.mkdir()
    (source / "grammar.js").write_text("module.exports = {}", encoding="utf-8")
    blocked = native if failing == "native" else legacy
    attempts = []
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        attempts.append(self)
        if self == blocked:
            raise PermissionError(13, "fixture denied unlink", str(self))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    tools = UserGrammarTools(build, sources)
    result = tools.remove_grammar("baml")
    steps = result["steps_completed"]
    require(result["status"] == "error", f"partial status {result!r}")
    denial = PermissionError(13, "fixture denied unlink", str(blocked))
    require(
        result["errors"] == [f"Failed to remove grammar: {denial}"],
        f"error names failed path {result['errors']!r}",
    )
    require((source / "grammar.js").is_file(), "source preserved")
    require(
        "Removed compiled grammar library: baml.so" not in steps,
        "no false legacy step",
    )
    if failing == "native":
        require(attempts == [native], f"legacy untouched {attempts!r}")
        require(legacy.read_bytes() == b"legacy", "legacy kept")
        require(steps == [], f"no removal steps {steps!r}")
    else:
        require(
            "Removed compiled grammar library: baml.dll" in steps,
            f"NATIVE_REMOVE_PROGRESS path step {steps!r}",
        )
        require(
            "Removed compiled grammar library" in steps,
            f"NATIVE_REMOVE_PROGRESS generic step {steps!r}",
        )
        require(not os.path.lexists(native), "native removed")
        require(legacy.read_bytes() == b"legacy", "legacy remains")
        require(tools.manager._library_path("baml") == legacy, "legacy now selected")


INVALID_LANGUAGES = [
    "",
    ".",
    "..",
    "../outside",
    "x/../../outside",
    "a/b",
    "a\\b",
    "x\\..\\..\\outside",
    "C:outside",
    "C:\\outside",
    "\\\\server\\share\\outside",
    "a\0b",
    "ABSOLUTE",
]


@pytest.mark.parametrize("language", INVALID_LANGUAGES)
def test_language_component_refuses_before_side_effects(tmp_path, language):
    if language == "ABSOLUTE":
        language = str(tmp_path / "absolute-outside")
    build, sources = _workspace(tmp_path)
    (build / "x").mkdir()
    (sources / "tree-sitter-x").mkdir()
    outside = {
        tmp_path / "outside.dll": b"outside native",
        tmp_path / "outside.so": b"outside legacy",
        tmp_path / "outside" / "keep.txt": b"outside source",
        tmp_path / "absolute-outside.dll": b"absolute native",
        tmp_path / "absolute-outside.so": b"absolute legacy",
    }
    for path, data in outside.items():
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
    calls = []

    def blocked(name):
        def spy(*args, **kwargs):
            calls.append((name, args))
            raise RuntimeError(f"blocked side effect {name}")

        return spy

    real_lexists = os.path.lexists

    def lexists(path):
        calls.append(("lexists", (path,)))
        return real_lexists(path)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            grammar_management, "_platform_library_suffix", lambda platform=None: ".dll"
        )
        tools = UserGrammarTools(build, sources)
        patch.setattr(grammar_management, "probe_native_grammar", blocked("probe"))
        patch.setattr(grammar_management.subprocess, "run", blocked("run"))
        patch.setattr(user_grammar_tools.subprocess, "run", blocked("run"))
        patch.setattr(user_grammar_tools.shutil, "copy2", blocked("copy2"))
        patch.setattr(user_grammar_tools.shutil, "rmtree", blocked("rmtree"))
        patch.setattr(Path, "unlink", blocked("unlink"))
        patch.setattr(os, "unlink", blocked("os.unlink"))
        patch.setattr(os, "remove", blocked("os.remove"))
        patch.setattr(os.path, "lexists", lexists)
        refusals = []
        for operation in (
            lambda: tools.manager.diagnose_grammar_issues(language),
            lambda: tools.manager.generate_recovery_plan(language),
            lambda: tools.manager._library_path(language),
            lambda: tools.get_grammar_info(language),
        ):
            try:
                operation()
            except ValueError as error:
                refusals.append(str(error))
            except RuntimeError as error:
                raise AssertionError(
                    f"LANGUAGE_COMPONENT_SIDE_EFFECT {language!r}: {error}"
                ) from error
        results = [
            tools.install_grammar(language, REPO_URL),
            tools.update_grammar(language),
            tools.remove_grammar(language),
        ]
    require(
        calls == [],
        f"LANGUAGE_COMPONENT_SIDE_EFFECT {language!r} reached {calls!r}",
    )
    require(len(refusals) == 4, f"manager refusals {refusals!r}")
    for result in results:
        require(result["status"] == "error", f"refused {result!r}")
        require(result["steps_completed"] == [], f"no steps {result!r}")
        require(
            any(
                "portable filename component" in e or "nonempty" in e
                for e in result["errors"]
            ),
            f"component error {result['errors']!r}",
        )
    for path, data in outside.items():
        require(path.read_bytes() == data, f"outside sentinel {path} unchanged")


def test_language_component_accepts_hyphen_and_underscore(tmp_path, monkeypatch):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    language = "my-lang_2"
    probes = _record_probes(monkeypatch)
    tools = UserGrammarTools(build, sources)
    health = tools.manager.diagnose_grammar_issues(language)
    require(health.status == "missing", f"valid name diagnosed {health!r}")
    # Rule 3: a candidate that does not exist is missing without a probe.
    require(probes == [], f"probe {probes!r}")
    (build / f"{language}.dll").write_bytes(b"native")
    (build / f"{language}.so").write_bytes(b"legacy")
    result = tools.remove_grammar(language)
    require(result["status"] == "success", f"valid remove {result!r}")
    require(not any(build.iterdir()), "valid pair removed")


def _git(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _commit(repository, message):
    _git(["git", "add", "-A"], repository)
    _git(
        [
            "git",
            "-c",
            "user.name=Native Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            message,
        ],
        repository,
    )


def _no_generate(args):
    if args == ["tree-sitter", "generate"]:
        # The fixture repository already contains its legacy library; this is
        # not a claim about the external generator's behavior.
        return [sys.executable, "-I", "-c", "pass"]
    return args


SHADOW_STATES = ["approved_native", "pinned_arbitrary", "empty", "directory"]
if os.name != "nt":
    SHADOW_STATES.append("dangling_symlink")


def _seed_shadow_native(native, state, baml_bytes):
    if state == "approved_native":
        native.write_bytes(baml_bytes)
    elif state == "pinned_arbitrary":
        native.write_bytes(b"arbitrary pinned native bytes")
    elif state == "empty":
        native.write_bytes(b"")
    elif state == "directory":
        native.mkdir()
    else:
        native.symlink_to(native.with_name("absent-target.dll"))


def _native_snapshot(native):
    if native.is_symlink():
        return ("symlink", native.readlink())
    if native.is_dir():
        return ("directory", sorted(p.name for p in native.iterdir()))
    return ("file", native.read_bytes())


@pytest.mark.parametrize("operation", ["install", "changed_update"])
@pytest.mark.parametrize("state", SHADOW_STATES)
def test_shadowed_legacy_copy_refused_before_install_or_changed_update(
    tmp_path, monkeypatch, baml_bytes, operation, state
):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    native = build / "baml.dll"
    legacy = build / "baml.so"
    require(native != legacy, "distinct native and legacy paths")
    _seed_shadow_native(native, state, baml_bytes)
    pins = {"baml": _pin(native.read_bytes() if native.is_file() else baml_bytes)}
    legacy_source = b"different legacy library bytes"
    real_run = subprocess.run
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["git", "init", "-b", "main"], upstream)
    _git(["git", "config", "core.longpaths", "true"], upstream)
    if operation == "install":
        (upstream / "baml.so").write_bytes(legacy_source)
        _commit(upstream, "fixture")

        def offline(args, **kwargs):
            if args[:2] == ["git", "clone"]:
                args = [*args[:-2], str(upstream), args[-1]]
            return real_run(_no_generate(args), **kwargs)

    else:
        (upstream / "grammar.js").write_text("module.exports = {}", encoding="utf-8")
        _commit(upstream, "initial")
        checkout = sources / "tree-sitter-baml"
        _git(["git", "clone", str(upstream), str(checkout)], tmp_path)
        _git(["git", "remote", "set-url", "origin", REPO_URL], checkout)
        (upstream / "baml.so").write_bytes(legacy_source)
        _commit(upstream, "changed")

        def offline(args, **kwargs):
            if args == ["git", "fetch", "origin"]:
                args = ["git", "fetch", str(upstream), "main:refs/remotes/origin/main"]
            return real_run(_no_generate(args), **kwargs)

    monkeypatch.setattr(user_grammar_tools.subprocess, "run", offline)
    before = _native_snapshot(native)
    probes = _record_probes(monkeypatch)
    tools = UserGrammarTools(build, sources, trusted_artifacts=pins)
    if operation == "install":
        result = tools.install_grammar("baml", REPO_URL)
        require("Cloned repository" in result["steps_completed"], f"cloned {result!r}")
    else:
        result = tools.update_grammar("baml")
        require(
            "Updated to latest version" in result["steps_completed"],
            f"changed revision reached {result!r}",
        )
    require(
        not os.path.lexists(legacy),
        f"SHADOW_NO_LEGACY_ENTRY {legacy} was written: {result!r}",
    )
    require(_native_snapshot(native) == before, "SHADOW_NATIVE_UNCHANGED")
    require(result["status"] == "error", f"SHADOW_REFUSED {result!r}")
    require(
        any(
            "Refusing to copy baml.so" in error and str(native) in error
            for error in result["errors"]
        ),
        f"shadow refusal names native {result['errors']!r}",
    )
    require(probes == [], f"no diagnosis after refusal {probes!r}")
    require(
        not any(
            "Copied" in step or "Updated compiled" in step
            for step in result["steps_completed"]
        ),
        f"no copy step {result!r}",
    )
    require(
        "Validated grammar installation" not in result["steps_completed"],
        "no misleading validation",
    )


@pytest.mark.parametrize("suffix", ["actual", ".dll"])
def test_selection_paths_never_load_unapproved_library_in_parent(
    tmp_path, monkeypatch, sentinel_bytes, suffix
):
    suffix = _simulate(monkeypatch, suffix)
    build, sources = _workspace(tmp_path)
    sentinel = tmp_path / "parent-entered"
    monkeypatch.setenv("CHUNKER_TEST_NATIVE_SENTINEL", str(sentinel))
    for name in (f"baml{suffix}", "baml.so", f"helper{suffix}"):
        (build / name).write_bytes(sentinel_bytes)
    tools = UserGrammarTools(build, sources)
    health = tools.manager.diagnose_grammar_issues("baml")
    validated = tools.manager.validate_all_grammars()
    listed = tools.list_installed_grammars()
    info = tools.get_grammar_info("baml")
    helper_info = tools.get_grammar_info("helper")
    plan = tools.manager.generate_recovery_plan("baml")
    require(not sentinel.exists(), "SELECTION_PARENT_LOAD sentinel entered")
    require(health.validation_reason == "untrusted", f"untrusted {health!r}")
    require(set(validated) == {"baml", "helper"}, f"validated {validated!r}")
    require(listed["healthy_grammars"] == 0, "nothing admitted")
    require(info["health"].status == "incompatible", "info not admitted")
    require(helper_info["health"].validation_reason == "untrusted", "helper untrusted")
    require(plan["current_status"] == "incompatible", "plan status")
    require(tools.manager.trusted_artifacts == {}, "no self-pin")
    control = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import ctypes, sys; ctypes.CDLL(sys.argv[1])",
            str(build / f"helper{suffix}"),
        ],
        check=False,
        capture_output=True,
        timeout=60,
        env={**os.environ, "CHUNKER_TEST_NATIVE_SENTINEL": str(sentinel)},
    )
    require(control.returncode == 0, f"isolated CDLL control {control.stderr!r}")
    require(sentinel.read_bytes() == b"entered", "isolated CDLL creates sentinel")


def test_recovery_plan_names_selected_library_without_glob(tmp_path, monkeypatch):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    manager = SmartGrammarManager(build, sources)
    missing = manager.generate_recovery_plan("baml")
    steps = missing["recovery_steps"]
    require(
        any(str(build / "baml.dll") in step for step in steps), f"missing {steps!r}"
    )
    require(not any("*" in step for step in steps), "no glob copy instruction")
    (build / "baml.so").write_bytes(b"")
    # Rule 3: pin the language so the empty file reaches the probe's check.
    manager.trusted_artifacts["baml"] = {"sha256": "0" * 64}
    corrupted = manager.generate_recovery_plan("baml")
    require(corrupted["current_status"] == "corrupted", f"corrupted {corrupted!r}")
    require(
        f"Remove the corrupted library file: {build / 'baml.so'}"
        in corrupted["recovery_steps"],
        f"selected legacy named {corrupted['recovery_steps']!r}",
    )
    require(not any("*" in step for step in corrupted["recovery_steps"]), "no glob")


@pytest.mark.parametrize("suffix", ["actual", ".dll"])
def test_native_named_public_info_and_diagnose_with_approved_tool(
    tmp_path, monkeypatch, capsys, baml_bytes, suffix
):
    suffix = _simulate(monkeypatch, suffix)
    build, sources = _workspace(tmp_path)
    library = build / f"baml{suffix}"
    library.write_bytes(baml_bytes)
    _isolated_parse(library)
    probes = _record_probes(monkeypatch)
    for command in ("info", "diagnose"):
        tools = UserGrammarTools(
            build, sources, trusted_artifacts={"baml": _pin(baml_bytes)}
        )
        code, out, err = _run_cli(
            monkeypatch, capsys, ["grammar", command, "baml"], tools
        )
        require("Status: ✅ healthy" in out, f"{command}: healthy report {out!r}")
        require("Recovery Plan" not in out, f"{command}: no recovery plan")
        require("Error" not in err, f"{command}: stderr {err!r}")
        require(code == 0, f"{command}: exit {code!r}")
        require(probes[-1] == library.absolute(), f"{command}: probe {probes!r}")
    # The second command reuses this process's fresh admission under the
    # frozen verdict key (same bytes, pin and inspector).
    require(len(probes) == 1, f"one probe per process {probes!r}")
    require(library.read_bytes() == baml_bytes, "fixture unchanged")


def test_validate_native_only_nonhealthy_exits_one(tmp_path, monkeypatch, capsys):
    _simulate(monkeypatch, ".dll")
    build, sources = _workspace(tmp_path)
    (build / "baml.dll").write_bytes(b"unpinned native bytes")
    tools = UserGrammarTools(build, sources)
    code, out, err = _run_cli(monkeypatch, capsys, ["grammar", "validate"], tools)
    require("Total grammars: 1" in out, f"native counted {out!r}")
    require("- baml: incompatible" in out, f"native reported {out!r}")
    require("Native admission failed: untrusted" in out, "untrusted reason")
    require(err == "", f"stderr {err!r}")
    require(code == 1, f"validate exit {code!r}")
    require(tools.manager.trusted_artifacts == {}, "no trust from name")
