"""Analyzer pin lookup and the retired dependency inspector (treesitter-chunker#362).

ADMIT SL-ins: ``GrammarAnalyzer.analyze_grammar_file`` passes only the one-field
``{"sha256": ...}`` record to ``probe_native_grammar`` (rule 3), stores and
reuses its inspector metadata only under its own inspector key
(``grammar_analyzer.v1``), and ``GrammarMetadataExtractor.extract_from_dependencies``
is retired (inventory A1): no tool runs. Native checks use the real BAML
grammar compiled from ``packages/baml-grammar/src``.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from chunker._internal.grammar_management import SmartGrammarManager
from chunker.grammar.integrity import probe_native_grammar
from chunker.languages.compatibility import grammar_analyzer
from chunker.languages.compatibility.grammar_analyzer import (
    GrammarAnalyzer,
    GrammarMetadataExtractor,
)
from tests.test_compiled_grammar_analysis_contract import SOURCE, _compile_probe_fixture


def require(condition: object, name: str) -> None:
    if not condition:
        raise AssertionError(name)


@pytest.fixture(scope="module")
def baml_bytes(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return _compile_probe_fixture(
        tmp_path_factory.mktemp("analyzer"), [SOURCE / "parser.c"]
    ).read_bytes()


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def recording(path, language, *, provenance, **kwargs):
        calls.append(
            {"path": Path(path), "language": language, "provenance": provenance}
        )
        return probe_native_grammar(path, language, provenance=provenance, **kwargs)

    monkeypatch.setattr(grammar_analyzer, "probe_native_grammar", recording)
    return calls


def _grammars(tmp_path: Path, data: bytes) -> Path:
    directory = tmp_path / "grammars"
    directory.mkdir()
    (directory / "baml.so").write_bytes(data)
    (directory / "other.so").write_bytes(b"other bytes")
    return directory


def test_analyzer_forwards_only_one_field_record(tmp_path, baml_bytes, probes):
    pin = {"sha256": sha256(baml_bytes).hexdigest()}
    analyzer = GrammarAnalyzer(
        _grammars(tmp_path, baml_bytes),
        trusted_artifacts={"baml": {**pin, "note": "ignored"}, "other": {"sha256": 7}},
    )
    version = analyzer.analyze_grammar_file("baml")
    require(version is not None, "pinned grammar analyzed")
    require(len(probes) == 1 and probes[0]["provenance"] == pin, f"{probes}")
    require(analyzer.analyze_grammar_file("other") is None, "non-str pin")
    require(
        analyzer._capabilities["other"]["validation_reason"] == "untrusted",
        f"{analyzer._capabilities['other']}",
    )
    require(len(probes) == 1, "a non-str pin never calls the probe")


def test_analyzer_metadata_is_reused_only_under_its_own_inspector(
    tmp_path, baml_bytes, probes
):
    directory = _grammars(tmp_path, baml_bytes)
    pins = {"baml": {"sha256": sha256(baml_bytes).hexdigest()}}
    # Another inspecting site admits the same bytes first, with other metadata.
    manager = SmartGrammarManager(
        directory, tmp_path / "sources", trusted_artifacts=pins
    )
    require(manager.diagnose_grammar_issues("baml").status == "healthy", "manager ok")
    analyzer = GrammarAnalyzer(directory, trusted_artifacts=pins)
    first = analyzer.analyze_grammar_file("baml")
    require(first is not None, "analyzer ran its own inspector")
    capabilities = analyzer._capabilities["baml"]
    # The manager's metadata holds only file_size; the analyzer's own
    # inspector also supplies version and symbols (symbol counts depend on
    # host tools such as nm, so only their presence is checked).
    require(capabilities["version"] is not None, f"own metadata {capabilities}")
    require(isinstance(capabilities["symbols_count"], int), f"{capabilities}")
    require(capabilities["file_size"] == len(baml_bytes), f"{capabilities}")
    probe_count = len(probes)
    second = analyzer.analyze_grammar_file("baml")
    require(second is not None and len(probes) == probe_count, "reused in-process")
    require(analyzer._capabilities["baml"] == capabilities, "same admitted metadata")


def test_dependency_inspection_is_retired(tmp_path, baml_bytes, monkeypatch):
    """A1: no tool runs at all (not merely: its result is discarded)."""
    import os
    import subprocess

    library = tmp_path / "baml.so"
    library.write_bytes(baml_bytes)
    calls: list[tuple[str, object]] = []

    def recorder(name):
        def record(*args, **kwargs):
            calls.append((name, args))
            raise AssertionError(f"tool run through {name}: {args}")

        return record

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, recorder(f"subprocess.{name}"))
    monkeypatch.setattr(os, "system", recorder("os.system"))
    monkeypatch.setattr(os, "popen", recorder("os.popen"))
    result = GrammarMetadataExtractor.extract_from_dependencies(library)
    require(calls == [], f"no tool runs, even if its failure is swallowed: {calls}")
    require(
        result == {"dependencies": [], "dependencies_status": "retired"},
        "retired, distinguishable from no dependencies",
    )


@pytest.mark.parametrize("nm_outcome", ["timeout", "exit_1"])
def test_transient_symbol_analysis_is_not_reused(
    tmp_path, baml_bytes, probes, monkeypatch, nm_outcome
):
    """An nm deadline expiry (``deadline_expired``) or a failed nm run
    (``failed``, exit 1) is reported for that call only; the next call
    re-inspects instead of reusing an empty symbol table (treesitter-chunker#207).
    Mutation ``failed_is_settled`` (store a failed analysis) fails the exit-1
    case.

    The transient result is never stored, so the other sites' verdicts for the
    same bytes are untouched: the manager does not probe again and the loader
    keeps its one admitted copy (contract: at most one copy per pair)."""
    import subprocess

    from chunker._internal import grammar_management as manager_module
    from chunker._internal import native_admission
    from chunker.grammar import integrity

    directory = _grammars(tmp_path, baml_bytes)
    pins = {"baml": {"sha256": sha256(baml_bytes).hexdigest()}}
    other_probes: list[str] = []

    def counting(site, real):
        def probe(*args, **kwargs):
            other_probes.append(site)
            return real(*args, **kwargs)

        return probe

    monkeypatch.setattr(
        manager_module,
        "probe_native_grammar",
        counting("manager", manager_module.probe_native_grammar),
    )
    monkeypatch.setattr(
        integrity,
        "probe_native_grammar",
        counting("loader", integrity.probe_native_grammar),
    )
    manager = SmartGrammarManager(
        directory, tmp_path / "sources", trusted_artifacts=pins
    )
    require(manager.diagnose_grammar_issues("baml").status == "healthy", "manager")
    loaded, copy = native_admission.admitted_private_copy(
        directory / "baml.so", "baml", pins
    )
    require(loaded.supported and copy is not None, f"loader {loaded}")
    require(other_probes == ["manager", "loader"], f"{other_probes}")
    roots = set(native_admission._copy_roots)

    real_run = subprocess.run

    def broken_nm(args, *rest, **kwargs):
        if args and args[0] == "nm":
            if nm_outcome == "timeout":
                raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 5.0))
            return subprocess.CompletedProcess(args, 1, "", "nm: simulated failure")
        return real_run(args, *rest, **kwargs)

    analyzer = GrammarAnalyzer(directory, trusted_artifacts=pins)
    with monkeypatch.context() as patched:
        # Run nm even on Windows, where the analysis is otherwise unavailable.
        patched.setattr(grammar_analyzer.platform, "system", lambda: "Linux")
        patched.setattr(grammar_analyzer.subprocess, "run", broken_nm)
        first = analyzer.analyze_grammar_file("baml")
    require(first is not None, "the transient analysis is still returned")
    require(len(probes) == 1, f"one analyzer probe {probes}")

    # The other sites still reuse their own verdicts.
    require(manager.diagnose_grammar_issues("baml").status == "healthy", "manager")
    again, same_copy = native_admission.admitted_private_copy(
        directory / "baml.so", "baml", pins
    )
    require(again.supported and same_copy == copy, f"same copy {same_copy} {copy}")
    require(other_probes == ["manager", "loader"], f"no re-probe {other_probes}")
    require(set(native_admission._copy_roots) == roots, "no second copy")

    second = analyzer.analyze_grammar_file("baml")
    require(second is not None, "re-inspected")
    require(len(probes) == 2, f"the expired analysis was not reused {probes}")

    fresh = GrammarAnalyzer(directory, trusted_artifacts=pins)
    require(fresh.analyze_grammar_file("baml") is not None, "new instance")
    require(len(probes) == 2, f"a settled analysis is reused {probes}")


def _package_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: bytes, record: bytes
) -> Path:
    """Our wheel's grammar directory with a RECORD entry for ``baml.so``
    (the analyzer always looks for ``<language>.so``)."""
    import base64
    from importlib.metadata import PathDistribution

    from chunker._internal import package_supplier

    site = tmp_path / "site"
    package = site / "chunker"
    build = package / "data" / "grammars" / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (build / "baml.so").write_bytes(data)
    dist_info = site / "treesitter_chunker-6.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: treesitter-chunker\nVersion: 6.0.0\n",
        encoding="utf-8",
    )
    encoded = base64.urlsafe_b64encode(sha256(record).digest()).rstrip(b"=")
    (dist_info / "RECORD").write_text(
        "chunker/__init__.py,,\n"
        f"chunker/data/grammars/build/baml.so,sha256={encoded.decode()},"
        f"{len(record)}\n",
        encoding="utf-8",
    )
    distribution = PathDistribution(dist_info)
    monkeypatch.setattr(package_supplier, "_package_distribution", lambda: distribution)
    monkeypatch.setattr(
        package_supplier, "_package_init_file", lambda: package / "__init__.py"
    )
    package_supplier._package_grammar_records.cache_clear()
    return build


@pytest.fixture
def clear_package_records():
    from chunker._internal import package_supplier

    package_supplier._package_grammar_records.cache_clear()
    yield
    package_supplier._package_grammar_records.cache_clear()


def test_analyzer_admits_record_verified_package_grammar_without_pin(
    tmp_path, baml_bytes, probes, monkeypatch, clear_package_records
):
    build = _package_wheel(tmp_path, monkeypatch, baml_bytes, baml_bytes)
    analyzer = GrammarAnalyzer(build, trusted_artifacts=None)
    require(analyzer.analyze_grammar_file("baml") is not None, "no pin needed")
    capabilities = analyzer._capabilities["baml"]
    require(capabilities["validation_reason"] == "ok", f"{capabilities}")
    require(
        capabilities["artifact_sha256"] == sha256(baml_bytes).hexdigest(),
        f"{capabilities}",
    )


def test_analyzer_record_mismatch_is_never_rescued_by_a_pin(
    tmp_path, baml_bytes, probes, monkeypatch, clear_package_records
):
    tampered = baml_bytes + b"appended after install"
    build = _package_wheel(tmp_path, monkeypatch, tampered, baml_bytes)
    analyzer = GrammarAnalyzer(
        build, trusted_artifacts={"baml": {"sha256": sha256(tampered).hexdigest()}}
    )
    require(analyzer.analyze_grammar_file("baml") is None, "refused")
    reason = analyzer._capabilities["baml"]["validation_reason"]
    require(reason == "integrity_mismatch", f"{reason}")
    require(probes == [], f"never probed {probes}")
