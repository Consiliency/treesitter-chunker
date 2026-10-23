"""Compiled grammar analysis reports real artifacts and absent languages."""

import json
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from chunker.grammar_management.core import load_compiled_grammar
from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer
from chunker.languages.compatibility.schema import (
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    LanguageVersion,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"


def trusted_artifacts(path: Path) -> dict[str, dict[str, str]]:
    return {"baml": {"sha256": sha256(path.read_bytes()).hexdigest()}}


def _compile_probe_fixture(tmp_path: Path, sources: list[Path]) -> Path:
    suffix = (
        ".dll"
        if sys.platform == "win32"
        else ".dylib" if sys.platform == "darwin" else ".so"
    )
    library = tmp_path / f"probe{suffix}"
    if sys.platform == "win32":
        vswhere = (
            Path(os.environ["PROGRAMFILES(X86)"])
            / "Microsoft Visual Studio/Installer/vswhere.exe"
        )
        installation = subprocess.check_output(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ],
            text=True,
        ).strip()
        vcvars = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
        environment = subprocess.check_output(
            f'cmd.exe /d /s /c ""{vcvars}" >nul && set"',
            text=True,
        )
        compiler_env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() not in {"PATH", "INCLUDE", "LIB", "LIBPATH"}
        }
        for line in environment.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.upper() in {"PATH", "INCLUDE", "LIB", "LIBPATH"}:
                compiler_env[key.upper()] = value
        compiler = shutil.which("cl", path=compiler_env["PATH"])
        assert compiler is not None, "MSVC compiler is required for native fixtures"
        command = [
            compiler,
            "/nologo",
            "/LD",
            f"/I{SOURCE}",
            *map(str, sources),
            "/link",
            f"/OUT:{library}",
        ]
    else:
        compiler_env = None
        command = [
            "cc",
            "-dynamiclib" if sys.platform == "darwin" else "-shared",
            "-fPIC",
            f"-I{SOURCE}",
            *map(str, sources),
            "-o",
            str(library),
        ]
    print(f"native_fixture_compiler={command[0]}", flush=True)
    compiled = subprocess.run(
        command, cwd=tmp_path, env=compiler_env, check=False, capture_output=True
    )
    assert compiled.returncode == 0, compiled.stderr.decode(errors="replace")
    assert library.is_file()
    print(
        json.dumps(
            {
                "native_fixture_path": str(library),
                "byte_length": library.stat().st_size,
                "sha256": sha256(library.read_bytes()).hexdigest(),
                "compiler": command[0],
            }
        ),
        flush=True,
    )
    return library


def test_portable_probe_parses_real_baml_and_releases_snapshot(tmp_path: Path) -> None:
    from chunker.grammar.integrity import probe_native_grammar

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    snapshots = []

    def inspect(snapshot: Path) -> None:
        assert snapshot != library
        assert snapshot.read_bytes() == library.read_bytes()
        snapshots.append(snapshot)

    result = probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        sample=FIXTURE.read_bytes(),
        inspect_artifact=inspect,
    )
    assert result.supported and result.reason == "ok"
    assert result.artifact_sha256 == sha256(library.read_bytes()).hexdigest()
    assert len(snapshots) == 1 and not snapshots[0].exists()
    assert (
        not load_compiled_grammar(library, "baml")
        .parse(FIXTURE.read_bytes())
        .root_node.has_error
    )


def test_failed_snapshot_inspection_rejects_and_cleans_real_grammar(tmp_path):
    from chunker.grammar.integrity import probe_native_grammar

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    snapshots = []

    def inspect(snapshot):
        snapshots.append(snapshot)
        assert snapshot.read_bytes() == library.read_bytes()
        raise ValueError("metadata extraction failed")

    result = probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        sample=FIXTURE.read_bytes(),
        inspect_artifact=inspect,
    )
    assert not result.supported and result.reason == "inspect_failed"
    assert result.artifact_sha256 is None
    assert len(snapshots) == 1 and not snapshots[0].exists()


@pytest.mark.parametrize("state", ["corrupt", "wrong_symbol", "null_language"])
def test_pinned_invalid_native_artifact_is_rejected(tmp_path, state):
    from chunker._internal.grammar_management import SmartGrammarManager
    from chunker.grammar.integrity import probe_native_grammar

    if state == "corrupt":
        library = tmp_path / "probe.so"
        library.write_bytes(b"reviewed corrupt native fixture")
    else:
        code = tmp_path / "invalid.c"
        name = "unrelated_symbol" if state == "wrong_symbol" else "tree_sitter_baml"
        code.write_text(
            "#ifdef _WIN32\n__declspec(dllexport)\n#endif\n"
            f"void *{name}(void) {{ return 0; }}\n",
            encoding="utf-8",
        )
        library = _compile_probe_fixture(tmp_path, [code])
    grammar = tmp_path / "baml.so"
    grammar.write_bytes(library.read_bytes())
    pins = trusted_artifacts(grammar)
    result = probe_native_grammar(grammar, "baml", provenance=pins["baml"])
    assert not result.supported and result.reason == "load_failed"
    assert result.artifact_sha256 is None
    health = SmartGrammarManager(
        tmp_path, tmp_path / "sources", trusted_artifacts=pins
    ).diagnose_grammar_issues("baml")
    assert health.status == "corrupted" and health.validation_reason == "load_failed"


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        ("exit(0);", "ack_missing"),
        ("_exit(0);", "ack_missing"),
        ("abort();", "child_failed"),
        ("PAUSE();", "timeout"),
    ],
)
def test_native_constructor_failure_never_admits_grammar(
    tmp_path: Path, monkeypatch, action: str, reason: str
) -> None:
    from chunker.grammar.integrity import probe_native_grammar

    sentinel = tmp_path / "entered"
    monkeypatch.setenv("CHUNKER_TEST_NATIVE_SENTINEL", str(sentinel))
    code = tmp_path / "constructor.c"
    code.write_text(
        """
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#include <process.h>
#include <crtdbg.h>
#define PAUSE() Sleep(60000)
#else
#include <unistd.h>
#include <sys/resource.h>
#define PAUSE() sleep(60)
#endif
static void enter(void) {
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
#else
    struct rlimit limit = {0, 0};
    setrlimit(RLIMIT_CORE, &limit);
#endif
    FILE *marker = fopen(getenv("CHUNKER_TEST_NATIVE_SENTINEL"), "wb");
    if (marker) { fputs("entered", marker); fclose(marker); }
    ACTION
}
#ifdef _WIN32
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) enter();
    return TRUE;
}
#else
__attribute__((constructor)) static void start(void) { enter(); }
#endif
""".replace(
            "ACTION", action
        ),
        encoding="utf-8",
    )
    library = _compile_probe_fixture(tmp_path, [code])
    untrusted = probe_native_grammar(library, "baml", provenance=None)
    assert not sentinel.exists(), "unapproved constructor entered native code"
    assert untrusted.reason == "untrusted"
    for invalid_pin in ({}, {"sha256": None}, {"sha256": "invalid"}, {"sha256": 1}):
        assert (
            probe_native_grammar(library, "baml", provenance=invalid_pin).reason
            == "untrusted"
        )
    assert not sentinel.exists()
    result = probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        timeout=10,
    )
    assert sentinel.read_bytes() == b"entered"
    assert not result.supported and result.reason == reason
    assert result.artifact_sha256 is None
    renamed = library.with_name("released" + library.suffix)
    library.rename(renamed)
    renamed.unlink()


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "nonce",
        "malformed",
        "numeric_flags",
        "failure_list",
        "nested",
        "oversized_integer",
        "duplicate_record",
    ],
)
def test_probe_rejects_altered_real_child_acknowledgment(
    tmp_path: Path, monkeypatch, fault: str
) -> None:
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    original = integrity._read_child
    calls = []

    def alter(*args, **kwargs):
        rc, stdout, stderr, timed_out, overflow = original(*args, **kwargs)
        assert rc == 0 and not timed_out and not overflow
        calls.append(json.loads(stdout))
        if fault == "duplicate":
            stdout = stdout.rstrip()[:-1] + b', "loader_returned": true}'
        elif fault in {"nonce", "numeric_flags"}:
            record = json.loads(stdout)
            if fault == "nonce":
                record["nonce"] = "wrong"
            else:
                record["loader_returned"] = record["parse_returned"] = 1
            stdout = json.dumps(record).encode()
        elif fault == "failure_list":
            record = json.loads(stdout)
            record["failure"] = []
            stdout = json.dumps(record).encode()
            rc = 1
        elif fault == "nested":
            stdout = b"[" * 2000 + b"0" + b"]" * 2000
        elif fault == "oversized_integer":
            stdout = b"9" * 5000
        elif fault == "duplicate_record":
            stdout += stdout
        else:
            stdout = b"not JSON"
        return rc, stdout, stderr, timed_out, overflow

    monkeypatch.setattr(integrity, "_read_child", alter)
    result = integrity.probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        sample=FIXTURE.read_bytes(),
    )
    assert len(calls) == 1 and calls[0]["parse_returned"]
    expected_reason = "child_failed" if fault == "failure_list" else "ack_invalid"
    assert not result.supported and result.reason == expected_reason
    assert result.artifact_sha256 is None


def test_probe_ignores_candidate_pythonpath_shadow(tmp_path: Path, monkeypatch) -> None:
    from chunker.grammar.integrity import probe_native_grammar

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    sentinel = tmp_path / "shadow-entered"
    (tmp_path / "sitecustomize.py").write_text(
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('entered')",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        sample=FIXTURE.read_bytes(),
    )
    assert result.supported
    assert not sentinel.exists()
    control = subprocess.run(
        [sys.executable, "-c", "pass"], cwd=tmp_path, check=False, capture_output=True
    )
    assert control.returncode == 0 and sentinel.read_text() == "entered"


def test_probe_inspects_snapshot_after_original_replacement(
    tmp_path: Path, monkeypatch
) -> None:
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    original_bytes = library.read_bytes()
    expected = trusted_artifacts(library)["baml"]
    original = integrity._read_child
    captured = []

    def replace(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result[0] == 0
        replacement = library.with_name("replacement" + library.suffix)
        replacement.write_bytes(b"replacement bytes")
        replacement.replace(library)
        return result

    monkeypatch.setattr(integrity, "_read_child", replace)
    result = integrity.probe_native_grammar(
        library,
        "baml",
        provenance=expected,
        sample=FIXTURE.read_bytes(),
        inspect_artifact=lambda path: captured.append(path.read_bytes()),
    )
    assert result.supported and captured == [original_bytes]
    assert result.artifact_sha256 == expected["sha256"]
    rejected = integrity.probe_native_grammar(library, "baml", provenance=expected)
    assert not rejected.supported and rejected.reason == "integrity_mismatch"


def test_probe_loads_snapshot_when_original_changes_before_child(
    tmp_path: Path, monkeypatch
) -> None:
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    expected = trusted_artifacts(library)["baml"]
    real_child = integrity._read_child
    entered = []

    def replace_then_load(command, cwd, timeout, **kwargs):
        library.write_bytes(b"replaced original")
        entered.append(True)
        return real_child(command, cwd, timeout, **kwargs)

    monkeypatch.setattr(integrity, "_read_child", replace_then_load)
    result = integrity.probe_native_grammar(
        library, "baml", provenance=expected, sample=FIXTURE.read_bytes()
    )
    assert entered == [True]
    assert result.supported and result.artifact_sha256 == expected["sha256"]


@pytest.mark.parametrize("consumer", ["analyzer", "manager"])
def test_native_consumers_revalidate_same_stat_replacement_and_removal(
    tmp_path: Path, consumer: str
) -> None:
    from chunker._internal.grammar_management import SmartGrammarManager

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    grammar = tmp_path / "baml.so"
    grammar.write_bytes(library.read_bytes())
    pins = trusted_artifacts(grammar)
    observation = None
    if consumer == "analyzer":
        owner = GrammarAnalyzer(tmp_path, trusted_artifacts=pins)

        def supported():
            nonlocal observation
            observation = owner.get_grammar_capabilities("baml")
            return observation["supported"]

    else:
        owner = SmartGrammarManager(
            tmp_path, tmp_path / "sources", trusted_artifacts=pins
        )

        def supported():
            nonlocal observation
            observation = owner.diagnose_grammar_issues("baml")
            return observation.status == "healthy"

    assert supported(), observation
    initial_stat = grammar.stat()
    original = grammar.read_bytes()
    grammar.write_bytes(b"x" * len(original))
    os.utime(grammar, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
    assert grammar.stat().st_size == initial_stat.st_size
    assert grammar.stat().st_mtime_ns == initial_stat.st_mtime_ns
    assert not supported(), observation
    grammar.write_bytes(original)
    assert supported(), observation
    owner.trusted_artifacts["baml"]["sha256"] = "0" * 64
    assert not supported(), observation
    owner.trusted_artifacts = pins
    assert supported(), observation
    grammar.unlink()
    assert not supported(), observation


@pytest.mark.parametrize("pin_state", ["missing", "stale"])
def test_real_repository_install_reports_failed_native_admission(
    tmp_path: Path, monkeypatch, pin_state: str
) -> None:
    from chunker._internal.user_grammar_tools import UserGrammarTools
    from chunker.grammar.integrity import probe_native_grammar

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    pins = trusted_artifacts(library)
    assert probe_native_grammar(
        library, "baml", provenance=pins["baml"], sample=FIXTURE.read_bytes()
    ).supported
    repository = tmp_path / "fixture-repository"
    repository.mkdir()
    (repository / "baml.so").write_bytes(library.read_bytes())
    (repository / "declarations.baml").write_bytes(FIXTURE.read_bytes())
    real_run = subprocess.run
    for args in (
        ["git", "init", "-b", "main"],
        ["git", "config", "core.longpaths", "true"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Native Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
    ):
        real_run(args, cwd=repository, check=True, capture_output=True)

    def offline_install(args, **kwargs):
        if args[:2] == ["git", "clone"]:
            args = [*args[:-2], str(repository), args[-1]]
        elif args == ["tree-sitter", "generate"]:
            # This boundary supplies a precompiled real grammar, not a claim
            # about the external generator's compilation behavior.
            args = [
                sys.executable,
                "-I",
                "-c",
                "from pathlib import Path; assert Path('baml.so').is_file()",
            ]
        return real_run(args, **kwargs)

    monkeypatch.setattr(
        "chunker._internal.user_grammar_tools.subprocess.run", offline_install
    )
    rejected_pins = {} if pin_state == "missing" else {"baml": {"sha256": "0" * 64}}
    build = tmp_path / "installed"
    build.mkdir()
    tools = UserGrammarTools(
        build, tmp_path / "sources", trusted_artifacts=rejected_pins
    )
    result = tools.install_grammar(
        "baml", "https://github.com/Consiliency/native-fixture.git"
    )
    assert result["status"] == "warning", result
    assert not result["errors"]
    assert "Cloned repository" in result["steps_completed"]
    assert "Copied baml.so to build directory" in result["steps_completed"]
    assert (build / "baml.so").read_bytes() == library.read_bytes()
    reason = "untrusted" if pin_state == "missing" else "integrity_mismatch"
    assert result["warnings"] == [
        f"Grammar installed but native admission failed: {reason}"
    ]


@pytest.mark.parametrize("artifact_state", ["missing", "stale_pin"])
def test_unchanged_real_repository_update_validates_installed_artifact(
    tmp_path: Path, monkeypatch, artifact_state: str
) -> None:
    from chunker._internal.user_grammar_tools import UserGrammarTools
    from chunker.grammar.integrity import probe_native_grammar

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    grammar = tmp_path / "baml.so"
    grammar.write_bytes(library.read_bytes())
    pins = trusted_artifacts(grammar)
    assert probe_native_grammar(
        grammar, "baml", provenance=pins["baml"], sample=FIXTURE.read_bytes()
    ).supported
    sources = tmp_path / "sources"
    checkout = sources / "tree-sitter-baml"
    checkout.mkdir(parents=True)
    (checkout / "declarations.baml").write_bytes(FIXTURE.read_bytes())
    real_run = subprocess.run
    for args in (
        ["git", "init", "-b", "main"],
        ["git", "config", "core.longpaths", "true"],
        ["git", "add", "declarations.baml"],
        [
            "git",
            "-c",
            "user.name=Native Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/Consiliency/native-fixture.git",
        ],
    ):
        real_run(args, cwd=checkout, check=True, capture_output=True)

    def offline_fetch(args, **kwargs):
        if args == ["git", "fetch", "origin"]:
            args = ["git", "fetch", str(checkout), "main:refs/remotes/origin/main"]
        return real_run(args, **kwargs)

    monkeypatch.setattr(
        "chunker._internal.user_grammar_tools.subprocess.run", offline_fetch
    )
    tools = UserGrammarTools(tmp_path, sources, trusted_artifacts=pins)
    if artifact_state == "missing":
        grammar.unlink()
    else:
        grammar.write_bytes(b"x" * grammar.stat().st_size)
    result = tools.update_grammar("baml")
    assert result["status"] == "warning", result
    assert "Fetched latest changes" in result["steps_completed"]
    assert any("already up to date" in warning for warning in result["warnings"])
    assert any("failed native admission" in warning for warning in result["warnings"])


@pytest.mark.skipif(sys.platform != "linux", reason="Analyzer inspects ELF .so symbols")
def test_local_baml_grammar_capabilities_and_missing_language(tmp_path: Path) -> None:
    grammar_path = tmp_path / "baml.so"
    metadata_source = tmp_path / "metadata.c"
    metadata_source.write_text(
        'const char *tree_sitter_baml_test_version = "grammar version 0.1.0";',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-Wl,--as-needed",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            str(metadata_source),
            "-o",
            str(grammar_path),
        ],
        check=True,
        capture_output=True,
    )
    source = FIXTURE.read_bytes()
    tree = load_compiled_grammar(grammar_path, "baml").parse(source)
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error

    assert GrammarAnalyzer(tmp_path).analyze_grammar_file("baml") is None
    analyzer = GrammarAnalyzer(
        tmp_path, trusted_artifacts=trusted_artifacts(grammar_path)
    )
    assert analyzer.supported_languages == ["baml"]
    grammar = analyzer.analyze_grammar_file("baml")
    assert grammar is not None
    assert grammar.language == "baml"
    assert grammar.grammar_file == str(grammar_path)
    assert grammar.version == "0.1.0"
    assert grammar.release_date is None
    capabilities = analyzer.get_grammar_capabilities("baml")
    assert capabilities["supported"] is True
    assert capabilities["version"] == grammar.version
    assert capabilities["file_size"] == grammar_path.stat().st_size
    assert capabilities["symbols_count"] > 0
    assert (
        capabilities["artifact_sha256"]
        == trusted_artifacts(grammar_path)["baml"]["sha256"]
    )

    assert analyzer.analyze_grammar_file("missing") is None
    missing = analyzer.get_grammar_capabilities("missing")
    assert missing["supported"] is False
    assert missing["version"] is None
    assert missing["symbols_count"] == 0
    assert missing["file_size"] == 0
    assert missing["validation_reason"] == "missing"

    report = analyzer.generate_grammar_report("baml")
    assert "Status: Supported" in report
    assert f"Version: {grammar.version}" in report
    assert f"Symbols Count: {capabilities['symbols_count']}" in report
    assert "Status: Not Supported" in analyzer.generate_grammar_report("missing")

    export_path = tmp_path / "analysis.json"
    analyzer.export_analysis_data(export_path)
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["metadata"]["total_languages"] == 1
    assert exported["grammars"]["baml"]["file"] == str(grammar_path)
    assert exported["grammars"]["baml"]["capabilities"]["supported"] is True
    assert exported["grammars"]["baml"]["capabilities"]["symbols_count"] > 0
    assert exported["validation_failures"] == {}
    assert (
        not load_compiled_grammar(grammar_path, "baml")
        .parse(source)
        .root_node.has_error
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="Fixture uses ELF linking and compiler comments"
)
def test_grammar_metadata_does_not_infer_versions_or_releases_from_mtime(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "baml.so"
    second = second_dir / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-Wl,--as-needed",
            "-o",
            str(first),
        ],
        check=True,
        capture_output=True,
    )
    # The existing string heuristics do not read ABI-15 semantic metadata.
    subprocess.run(
        ["objcopy", "--remove-section=.comment", str(first)],
        check=True,
        capture_output=True,
    )
    tree = load_compiled_grammar(first, "baml").parse(FIXTURE.read_bytes())
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error
    assert tree.root_node.named_child_count > 0
    second.write_bytes(first.read_bytes())
    os.utime(first, (1609459200, 1609459200))
    os.utime(second, (1640995200, 1640995200))
    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_mtime != second.stat().st_mtime

    for directory, artifact in ((first_dir, first), (second_dir, second)):
        analyzer = GrammarAnalyzer(
            directory, trusted_artifacts=trusted_artifacts(artifact)
        )
        assert analyzer.extract_grammar_version(artifact) is None
        grammar = analyzer.analyze_grammar_file("baml")
        assert grammar is not None
        assert grammar.version == "unknown"
        assert grammar.release_date is None
        assert grammar.to_dict()["release_date"] is None
        for constraint in (">=1.0", "<=1.0", "1.0-2.0"):
            rule = CompatibilityRule(
                "baml", "*", constraint, CompatibilityLevel.INCOMPATIBLE
            )
            assert not rule.matches_grammar_version(grammar)
            schema = CompatibilitySchema()
            schema.add_grammar_version(grammar)
            schema.add_compatibility_rule(rule)
            assert (
                schema.find_compatible_grammar(LanguageVersion("baml", "1.0"))
                is grammar
            )
        assert "Version: unknown" in analyzer.generate_grammar_report("baml")
        export = directory / "analysis.json"
        analyzer.export_analysis_data(export)
        exported = json.loads(export.read_text(encoding="utf-8"))
        assert exported["grammars"]["baml"]["version"] == "unknown"
        assert exported["grammars"]["baml"]["capabilities"]["version"] == "unknown"


def test_analyzer_rejects_partial_inspection_and_preserves_failure_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grammar_path = tmp_path / "baml.so"
    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    if library != grammar_path:
        grammar_path.write_bytes(library.read_bytes())
    analyzer = GrammarAnalyzer(
        tmp_path, trusted_artifacts=trusted_artifacts(grammar_path)
    )

    def inspect_raises(_: Path) -> str:
        raise RuntimeError("inspection failed")

    monkeypatch.setattr(analyzer, "extract_grammar_version", inspect_raises)
    assert analyzer.analyze_grammar_file("baml") is None
    capabilities = analyzer.get_grammar_capabilities("baml")
    assert capabilities["supported"] is False
    assert capabilities["validation_reason"] == "inspect_failed"

    export_path = tmp_path / "analysis.json"
    analyzer.export_analysis_data(export_path)
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["grammars"] == {}
    assert (
        exported["validation_failures"]["baml"]["validation_reason"] == "inspect_failed"
    )


def _wait_for_file(path, process=None, timeout=45):
    import time

    deadline = time.monotonic() + timeout
    while not path.exists() or path.stat().st_size == 0:
        if process is not None and process.poll() is not None:
            if path.exists() and path.stat().st_size:
                return
            raise AssertionError(
                f"supervised controller exited before {path.name}: {process.communicate(timeout=5)}"
            )
        assert time.monotonic() < deadline, f"missing barrier: {path}"
        time.sleep(0.01)


def test_native_marker_published_at_controller_exit_is_observed(tmp_path):
    marker = tmp_path / "returned"

    class ExitingController:
        def poll(self):
            pending = marker.with_suffix(".tmp")
            pending.write_text('{"complete": true}', encoding="utf-8")
            pending.replace(marker)
            return 0

    _wait_for_file(marker, ExitingController())
    assert json.loads(marker.read_text(encoding="utf-8")) == {"complete": True}


class _NativeObserver:
    """Driver-owned oracle, independent of production bookkeeping and reaping."""

    def __init__(self, pid, creation):
        import psutil

        self.process = psutil.Process(pid)
        self.process.create_time()
        self.handle = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            self.ctypes = ctypes
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            signatures = {
                "OpenProcess": (
                    [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                    wintypes.HANDLE,
                ),
                "GetProcessTimes": (
                    [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4,
                    wintypes.BOOL,
                ),
                "WaitForSingleObject": (
                    [wintypes.HANDLE, wintypes.DWORD],
                    wintypes.DWORD,
                ),
                "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(self.api, name)
                function.argtypes, function.restype = arguments, result
            self.handle = self.api.OpenProcess(0x100000 | 0x1000, False, pid)
            assert self.handle, ctypes.get_last_error()
            times = [wintypes.FILETIME() for _ in range(4)]
            assert self.api.GetProcessTimes(
                self.handle, *(ctypes.byref(t) for t in times)
            )
            actual = f"{(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime:016x}"
            self.creation = actual
            if creation is not None:
                assert actual == creation
        assert self.alive(), "observer must be acquired while fixture is alive"

    def alive(self):
        import psutil

        if self.handle is not None:
            result = self.api.WaitForSingleObject(self.handle, 0)
            assert result in {0, 258}, self.ctypes.get_last_error()
            return result == 258
        try:
            return (
                self.process.is_running()
                and self.process.status() != psutil.STATUS_ZOMBIE
            )
        except psutil.NoSuchProcess:
            return False

    def close(self):
        if self.handle is not None:
            assert self.api.CloseHandle(self.handle)
            self.handle = None


@pytest.mark.parametrize("fault", ["timeout", "stdout_overflow", "stderr_overflow"])
def test_native_probe_worker_exits_before_snapshot_cleanup(tmp_path, fault):
    import time

    code = tmp_path / "native_open.c"
    code.write_text(
        r"""
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#include <process.h>
static HANDLE opened;
#define PID _getpid()
#define PAUSE() Sleep(10)
static void enter(HMODULE module) {
    char path[32768];
    if (!GetModuleFileNameA(module, path, sizeof(path))) abort();
    opened = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (opened == INVALID_HANDLE_VALUE) abort();
#else
#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
static int opened;
#define PID getpid()
#define PAUSE() usleep(10000)
static void enter(void) {
    Dl_info info;
    if (!dladdr((void *)enter, &info)) abort();
    const char *path = info.dli_fname;
    opened = open(path, O_RDONLY);
    if (opened < 0) abort();
#endif
    const char *marker_path = getenv("CHUNKER_TEST_OPEN_MARKER");
    char pending[32768];
    int length = snprintf(pending, sizeof(pending), "%s.%ld.tmp", marker_path, (long)PID);
    if (length < 0 || length >= sizeof(pending)) abort();
    FILE *marker = fopen(pending, "wb");
    if (!marker) abort();
    fprintf(marker, "%ld\n%s\n", (long)PID, path);
    if (fclose(marker) || rename(pending, marker_path)) abort();
    const char *trigger = getenv("CHUNKER_TEST_OPEN_TRIGGER");
    for (;;) {
        FILE *release = fopen(trigger, "rb");
        if (release) { fclose(release); break; }
        PAUSE();
    }
    int descriptor = atoi(getenv("CHUNKER_TEST_OPEN_DESCRIPTOR"));
    if (descriptor) {
        FILE *output = descriptor == 1 ? stdout : stderr;
        for (int i = 0; i < 131072; ++i) fputc('x', output);
        fflush(output);
    }
    for (;;) PAUSE();
}
#ifdef _WIN32
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) enter(module);
    return TRUE;
}
#else
__attribute__((constructor)) static void start(void) { enter(); }
#endif
""",
        encoding="utf-8",
    )
    library = _compile_probe_fixture(tmp_path, [code])
    pin = trusted_artifacts(library)["baml"]
    marker, trigger, cleanup, release, returned, return_observed = [
        tmp_path / name
        for name in (
            "opened",
            "trigger",
            "cleanup",
            "release",
            "returned",
            "return-observed",
        )
    ]
    driver = tmp_path / "driver.py"
    driver.write_text(
        """
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chunker.grammar import integrity
library, cleanup, release, returned, return_observed = map(Path, sys.argv[2:7])
original = integrity.shutil.rmtree
observed = {}
def publish(path, record):
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(record), encoding="utf-8")
    pending.replace(path)
def wait(path):
    deadline = time.monotonic() + 45
    while not path.exists():
        if time.monotonic() > deadline: raise RuntimeError("driver did not release " + path.name)
        time.sleep(0.01)
def remove(path, *args, **kwargs):
    publish(cleanup, {"root": str(path), "launcher_reaped": observed["state"].launcher.returncode is not None})
    wait(release)
    return original(path, *args, **kwargs)
original_read = integrity._read_child
def read(*args, **kwargs):
    observed["state"] = kwargs["lifecycle"]
    return original_read(*args, **kwargs)
integrity._read_child = read
integrity.shutil.rmtree = remove
result = integrity.probe_native_grammar(library, "baml", provenance={"sha256": sys.argv[7]}, timeout=12)
s = observed["state"]
record = {"reason": result.reason, "digest": result.artifact_sha256, "launcher": s.launcher.pid, "worker": s.worker.pid if s.worker else None, "launcher_reaped": s.launcher.returncode is not None}
publish(returned, record)
wait(return_observed)
print(json.dumps(record), flush=True)
""",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment.update(
        {
            "CHUNKER_TEST_OPEN_MARKER": str(marker),
            "CHUNKER_TEST_OPEN_TRIGGER": str(trigger),
            "CHUNKER_TEST_OPEN_DESCRIPTOR": str(
                {"timeout": 0, "stdout_overflow": 1, "stderr_overflow": 2}[fault]
            ),
        }
    )
    controller = subprocess.Popen(
        [
            sys.executable,
            "-I",
            str(driver),
            str(ROOT),
            str(library),
            str(cleanup),
            str(release),
            str(returned),
            str(return_observed),
            pin["sha256"],
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observer = None
    snapshot = None
    try:
        _wait_for_file(marker, controller)
        lines = marker.read_text(encoding="utf-8").splitlines()
        pid, snapshot = int(lines[0]), Path(lines[1])
        assert snapshot != library and snapshot.parent.name.startswith(
            "chunker-native-probe-"
        )
        assert sha256(snapshot.read_bytes()).hexdigest() == pin["sha256"]
        ready = json.loads(
            (snapshot.parent / ".native-probe-worker.json").read_text(encoding="utf-8")
        )
        assert ready["pid"] == pid
        observer = _NativeObserver(pid, ready["windows_creation_filetime"])
        if fault != "timeout":
            trigger.touch()
        cleanup_deadline = time.monotonic() + 45
        while not cleanup.exists() and not returned.exists():
            if controller.poll() is not None:
                break
            assert (
                time.monotonic() < cleanup_deadline
            ), "controller did not reach cleanup or return"
            time.sleep(0.01)
        before = (
            observer.alive() if cleanup.exists() and cleanup.stat().st_size else None
        )
        cleanup_record = (
            json.loads(cleanup.read_text(encoding="utf-8"))
            if before is not None
            else None
        )
        release.touch()
        _wait_for_file(returned, controller)
        return_record = json.loads(returned.read_text(encoding="utf-8"))
        at_return = observer.alive()
        return_observed.touch()
        stdout, stderr = controller.communicate(timeout=45)
        # Capture both oracle values before emergency cleanup, even on unlink failure.
        print(
            json.dumps(
                {
                    "native_open_observation": True,
                    "fault": fault,
                    "worker": pid,
                    "snapshot": str(snapshot),
                    "sha256": pin["sha256"],
                    "alive_before_cleanup": before,
                    "actual_worker_alive_at_return": at_return,
                    "return_observation": "post-probe barrier before controller exit",
                }
            ),
            flush=True,
        )
        assert before is not True and not at_return, {
            "actual_worker_alive_before_cleanup": before,
            "actual_worker_alive_at_return": at_return,
            "stderr": stderr,
        }
        assert controller.returncode == 0, stderr
        result = json.loads(stdout)
        assert result == return_record
        assert result["reason"] == ("timeout" if fault == "timeout" else "ack_invalid")
        assert result["digest"] is None and result["worker"] == pid
        assert (
            cleanup_record is not None
            and cleanup_record["launcher_reaped"]
            and result["launcher_reaped"]
        )
        if sys.platform == "win32":
            assert (
                result["launcher"] != pid
            ), "affected real venv redirector topology is required"
        assert not snapshot.parent.exists()
        renamed = library.with_name("released" + library.suffix)
        library.rename(renamed)
        renamed.unlink()
        print(
            json.dumps(
                {
                    "fault": fault,
                    "snapshot": str(snapshot),
                    "sha256": pin["sha256"],
                    "worker": pid,
                    "launcher": result["launcher"],
                    "alive_before_cleanup": before,
                    "alive_at_return": at_return,
                    "python": sys.version,
                    "executable": sys.executable,
                    "base_executable": sys._base_executable,
                }
            ),
            flush=True,
        )
    finally:
        release.touch()
        return_observed.touch()
        if observer is not None:
            if observer.alive():
                observer.process.kill()
                emergency_deadline = time.monotonic() + 10
                while observer.alive():
                    assert (
                        time.monotonic() < emergency_deadline
                    ), "emergency worker cleanup failed"
                    time.sleep(0.01)
            observer.close()
        if controller.poll() is None:
            controller.kill()
        controller.communicate(timeout=10)
        if snapshot is not None and snapshot.parent.exists():
            shutil.rmtree(snapshot.parent)


@pytest.mark.parametrize("status", ["zero", "abnormal", "unavailable"])
def test_native_actual_worker_status_required_after_real_ack(
    tmp_path, monkeypatch, status
):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    original_read, original_exited = integrity._read_child, integrity._worker_exited
    observed, inspected = [], []

    def read(command, cwd, timeout, **kwargs):
        if status == "abnormal":
            command = list(command)
            command[3] = command[3].replace(
                "raise SystemExit(_native_probe_child(*sys.argv[2:]))",
                "import os; result = _native_probe_child(*sys.argv[2:]); sys.stdout.flush(); os._exit(7)",
            )
        result = original_read(command, cwd, timeout, **kwargs)
        state = kwargs["lifecycle"]
        observed.append(
            (
                state.worker_status,
                state.launcher.returncode,
                state.cleanup_safe,
                json.loads(result[1]),
            )
        )
        return result

    def exited(state):
        done = original_exited(state)
        if done and status == "unavailable":
            state.worker_status = None
        return done

    monkeypatch.setattr(integrity, "_read_child", read)
    monkeypatch.setattr(integrity, "_worker_exited", exited)
    result = integrity.probe_native_grammar(
        library,
        "baml",
        provenance=trusted_artifacts(library)["baml"],
        sample=FIXTURE.read_bytes(),
        inspect_artifact=inspected.append,
    )
    worker_status, launcher_status, safe, ack = observed[0]
    assert ack["loader_returned"] is True and ack["parse_returned"] is True
    assert safe
    if status == "zero":
        assert result.supported and worker_status == launcher_status == 0
        assert len(inspected) == 1 and not inspected[0].exists()
    else:
        assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert not inspected
        assert worker_status == (7 if status == "abnormal" else None)


def test_native_valid_ack_abnormal_worker_launcher_zero(tmp_path, monkeypatch):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    original_read = integrity._read_child
    states, replies, roots = [], [], []
    launcher = tmp_path / "fault_launcher.py"
    launcher.write_text(
        "import subprocess,sys; child=subprocess.Popen([sys._base_executable,*sys.argv[1:]], stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=sys.stderr.buffer); child.wait(); raise SystemExit(0)",
        encoding="utf-8",
    )

    def read(command, cwd, timeout, **kwargs):
        import sysconfig

        command = list(command)
        # The fault worker directly uses the base interpreter; supply this test
        # environment's approved dependencies without another venv redirector.
        command[3] = (
            "import sys; sys.path.insert(0, "
            + repr(sysconfig.get_path("purelib"))
            + "); "
            + command[3]
        ).replace(
            "raise SystemExit(_native_probe_child(*sys.argv[2:]))",
            "import os; result=_native_probe_child(*sys.argv[2:]); sys.stdout.flush(); os._exit(7)",
        )
        states.append(kwargs["lifecycle"])
        roots.append(cwd)
        result = original_read(
            [sys._base_executable, "-I", str(launcher), *command[1:]],
            cwd,
            timeout,
            **kwargs,
        )
        replies.append(result)
        return result

    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        result = integrity.probe_native_grammar(
            library,
            "baml",
            provenance=trusted_artifacts(library)["baml"],
            sample=FIXTURE.read_bytes(),
        )
        if sys.platform == "win32" and states[0].worker is not None:
            print(
                json.dumps(
                    {
                        "actual_worker_status_control": True,
                        "worker_status": states[0].worker_status,
                        "launcher_status": replies[0][0],
                        "ack": json.loads(replies[0][1]),
                        "result": result.reason,
                    }
                ),
                flush=True,
            )
        assert result.reason == "child_failed" and result.artifact_sha256 is None
        if sys.platform == "win32":
            assert states[0].worker is not None, replies
            assert states[0].worker.pid != states[0].launcher.pid
            assert states[0].worker_status == 7 and replies[0][0] == 0
            assert json.loads(replies[0][1])["parse_returned"] is True
            assert states[0].cleanup_safe and not roots[0].exists()
        else:
            assert states[0].worker is None and not states[0].cleanup_safe
            assert not replies and roots[0].exists()
    finally:
        for root in roots:
            if root.exists():
                shutil.rmtree(root)


def test_native_handle_acquisition_precedes_start(tmp_path, monkeypatch):
    import psutil
    from types import SimpleNamespace
    from chunker.grammar import integrity

    worker = subprocess.Popen(
        [sys._base_executable, "-I", "-c", "import time; time.sleep(60)"],
        stdin=subprocess.PIPE,
    )
    identity = psutil.Process(worker.pid)
    events = []
    candidate_creation = "0123456789abcdef"

    class Candidate:
        def __init__(self, pid):
            assert pid == worker.pid
            events.append("open")

        def creation(self):
            events.append("creation")
            return candidate_creation

        def exited(self):
            events.append("wait")
            return False

        def terminate(self):
            events.append("terminate")
            pytest.fail("unarmed candidate cannot be signaled")

        def close(self):
            events.append("close")

    monkeypatch.setattr(integrity, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(integrity, "_WindowsProcess", Candidate)
    record = {
        "pid": worker.pid,
        "ppid": identity.ppid(),
        "windows_creation_filetime": "0000000000000000",
    }
    state = integrity._ProbeLifecycle(
        launch_attempted=True, launcher=worker, known={worker.pid: identity}
    )
    try:
        with pytest.raises(ValueError, match="identity mismatch"):
            integrity._register_worker(state, record)
        assert events == ["open", "creation", "close"]
        assert (
            state.worker_handle is None
            and not state.discovery_complete
            and worker.poll() is None
        )
        events.clear()
        record["windows_creation_filetime"] = candidate_creation
        integrity._register_worker(state, record)
        assert events == ["open", "creation", "wait"]
        assert state.worker_handle is not None and state.discovery_complete
        # Transfer completed before the controller can grant the start byte.
        state.aborted = True
        with pytest.raises(ValueError, match="launcher lost"):
            integrity._register_worker(state, record)
        assert events == [
            "open",
            "creation",
            "wait",
        ], "late registration cannot reopen by PID"
        state.worker_handle.close()
    finally:
        worker.kill()
        worker.wait(timeout=10)
        worker.stdin.close()


def test_analyzer_inspects_admitted_snapshot_after_original_replacement(
    tmp_path, monkeypatch
):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    grammar = tmp_path / "baml.so"
    original_bytes = library.read_bytes()
    grammar.write_bytes(original_bytes)
    pins = trusted_artifacts(grammar)
    analyzer = GrammarAnalyzer(tmp_path, trusted_artifacts=pins)
    real_child = integrity._read_child
    entered = []

    def replace(command, cwd, timeout, **kwargs):
        result = real_child(command, cwd, timeout, **kwargs)
        assert result[0] == 0 and json.loads(result[1])["parse_returned"] is True
        entered.append(True)
        grammar.write_bytes(b"replaced original metadata")
        return result

    monkeypatch.setattr(integrity, "_read_child", replace)
    monkeypatch.setattr(
        analyzer,
        "extract_grammar_version",
        lambda path: "0.1.0" if path.read_bytes() == original_bytes else "9.9.9",
    )
    result = analyzer.analyze_grammar_file("baml")
    assert entered == [True]
    assert result is not None and result.version == "0.1.0"
    capabilities = analyzer._capabilities["baml"]
    assert capabilities["file_size"] == len(original_bytes)
    assert capabilities["artifact_sha256"] == pins["baml"]["sha256"]


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_native_registered_read_fault_retains_root_and_original_exception(
    tmp_path, monkeypatch, error_type
):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    original_read, original_exited = integrity._read_child, integrity._worker_exited
    observed, roots, states = [], [], []
    fault = error_type("original registered read fault")

    def exited(state):
        if state.worker is not None and not observed:
            observed.append(state.worker.pid)
            raise fault
        return original_exited(state)

    def read(command, cwd, timeout, **kwargs):
        roots.append(cwd)
        states.append(kwargs["lifecycle"])
        try:
            return original_read(command, cwd, timeout, **kwargs)
        except error_type as error:
            assert error is fault
            raise

    monkeypatch.setattr(integrity, "_worker_exited", exited)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        if error_type is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt) as raised:
                integrity.probe_native_grammar(
                    library, "baml", provenance=trusted_artifacts(library)["baml"]
                )
            assert raised.value is fault
        else:
            result = integrity.probe_native_grammar(
                library, "baml", provenance=trusted_artifacts(library)["baml"]
            )
            assert result.reason == "child_failed" and result.artifact_sha256 is None
        assert len(observed) == 1 and roots[0].exists() and not states[0].cleanup_safe
        assert states[0].launcher.poll() is not None
    finally:
        for root in roots:
            if root.exists():
                shutil.rmtree(root)


@pytest.mark.skipif(
    sys.platform != "win32", reason="Retained public Win32 worker handle status fault"
)
@pytest.mark.parametrize("operation", ["status", "wait"])
def test_native_windows_handle_failure_after_real_ack_rejects(
    tmp_path, monkeypatch, operation
):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    real_status, real_exited, real_read = (
        integrity._WindowsProcess.status,
        integrity._WindowsProcess.exited,
        integrity._read_child,
    )
    failures, observations, roots = [], [], []

    def status(handle):
        if operation == "status":
            failures.append("status")
            raise OSError("GetExitCodeProcess unavailable")
        return real_status(handle)

    def exited(handle):
        done = real_exited(handle)
        if done and operation == "wait" and not failures:
            failures.append("wait")
            raise OSError("WaitForSingleObject unavailable")
        return done

    def read(*args, **kwargs):
        roots.append(args[1])
        try:
            result = real_read(*args, **kwargs)
            observations.append(json.loads(result[1]))
            return result
        except OSError:
            # The real native worker and handle have run; stdout is drained before status polling.
            assert failures == ["wait"]
            raise

    monkeypatch.setattr(integrity._WindowsProcess, "status", status)
    monkeypatch.setattr(integrity._WindowsProcess, "exited", exited)
    monkeypatch.setattr(integrity, "_read_child", read)
    try:
        result = integrity.probe_native_grammar(
            library,
            "baml",
            provenance=trusted_artifacts(library)["baml"],
            sample=FIXTURE.read_bytes(),
            inspect_artifact=lambda _: pytest.fail(
                "inspection after unavailable status"
            ),
        )
        assert (
            failures
            and result.reason == "child_failed"
            and result.artifact_sha256 is None
        )
        if operation == "status":
            assert observations[0]["parse_returned"] is True
    finally:
        for root in roots:
            if root.exists():
                shutil.rmtree(root)


def test_native_child_rechecks_snapshot_digest_before_constructor(
    tmp_path, monkeypatch
):
    from chunker.grammar import integrity

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    library = _compile_probe_fixture(first, [SOURCE / "parser.c"])
    sentinel = tmp_path / "child-unapproved-constructor"
    code = second / "constructor.c"
    code.write_text(
        """
#include <stdio.h>
static void enter(void) {
    FILE *marker = fopen(SENTINEL, "wb");
    if (marker) { fputs("entered", marker); fclose(marker); }
}
#ifdef _WIN32
#include <windows.h>
__declspec(dllexport) void *tree_sitter_baml(void) { return NULL; }
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) enter();
    return TRUE;
}
#else
void *tree_sitter_baml(void) { return NULL; }
__attribute__((constructor)) static void start(void) { enter(); }
#endif
""".replace(
            "SENTINEL", json.dumps(str(sentinel))
        ),
        encoding="utf-8",
    )
    replacement = _compile_probe_fixture(second, [code])
    original = integrity._read_child
    entered = []

    def replace(command, cwd, timeout, **kwargs):
        entered.append(True)
        Path(command[5]).write_bytes(replacement.read_bytes())
        return original(command, cwd, timeout, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(integrity, "_read_child", replace)
        result = integrity.probe_native_grammar(
            library, "baml", provenance=trusted_artifacts(library)["baml"]
        )
    assert entered == [True] and result.reason == "load_failed"
    assert result.artifact_sha256 is None and not sentinel.exists()
    control = integrity.probe_native_grammar(
        replacement, "baml", provenance=trusted_artifacts(replacement)["baml"]
    )
    assert control.reason == "load_failed" and sentinel.read_bytes() == b"entered"


@pytest.mark.parametrize("cleanup_error", [OSError, KeyboardInterrupt])
def test_native_inspection_cancellation_survives_owner_cleanup_error(
    tmp_path, monkeypatch, cleanup_error
):
    from chunker.grammar import integrity

    library = _compile_probe_fixture(tmp_path, [SOURCE / "parser.c"])
    snapshots = []
    cancellation = KeyboardInterrupt("original inspection cancellation")

    def inspect(snapshot):
        snapshots.append(snapshot)
        raise cancellation

    def cleanup(_root):
        raise cleanup_error("owner cleanup failed")

    try:
        with monkeypatch.context() as context:
            context.setattr(integrity.shutil, "rmtree", cleanup)
            with pytest.raises(KeyboardInterrupt) as caught:
                integrity.probe_native_grammar(
                    library,
                    "baml",
                    provenance=trusted_artifacts(library)["baml"],
                    inspect_artifact=inspect,
                )
            assert caught.value is cancellation
            assert snapshots[0].exists()
    finally:
        for snapshot in snapshots:
            if snapshot.parent.exists():
                shutil.rmtree(snapshot.parent)
