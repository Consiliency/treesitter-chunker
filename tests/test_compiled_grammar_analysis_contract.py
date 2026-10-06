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
    subprocess.run(
        command, cwd=tmp_path, env=compiler_env, check=True, capture_output=True
    )
    assert library.is_file()
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
    assert probe_native_grammar(library, "baml", provenance=None).reason == "untrusted"
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

    def alter(*args):
        rc, stdout, stderr, timed_out, overflow = original(*args)
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

    def replace(*args):
        result = original(*args)
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

    def replace_then_load(command, cwd, timeout):
        library.write_bytes(b"replaced original")
        entered.append(True)
        return real_child(command, cwd, timeout)

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
    if consumer == "analyzer":
        owner = GrammarAnalyzer(tmp_path, trusted_artifacts=pins)

        def supported():
            return owner.get_grammar_capabilities("baml")["supported"]

    else:
        owner = SmartGrammarManager(
            tmp_path, tmp_path / "sources", trusted_artifacts=pins
        )

        def supported():
            return owner.diagnose_grammar_issues("baml").status == "healthy"

    assert supported()
    initial_stat = grammar.stat()
    original = grammar.read_bytes()
    grammar.write_bytes(b"x" * len(original))
    os.utime(grammar, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
    assert grammar.stat().st_size == initial_stat.st_size
    assert grammar.stat().st_mtime_ns == initial_stat.st_mtime_ns
    assert not supported()
    grammar.write_bytes(original)
    assert supported()
    owner.trusted_artifacts["baml"]["sha256"] = "0" * 64
    assert not supported()
    owner.trusted_artifacts = pins
    assert supported()
    grammar.unlink()
    assert not supported()


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
