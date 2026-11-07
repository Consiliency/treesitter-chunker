"""Caller samples count as compatibility evidence (treesitter-chunker#133).

A grammar without built-in validation samples gets the validator warning
``No test samples available for <language>``. That warning is an evidence
gap, not a performance finding: it must not classify a candidate as
``DEGRADED`` by itself. Caller-supplied samples parsed with the real artifact
are the evidence. Named mutations: ``M133-gap-degrades`` (treat the gap as a
quality warning, the old behavior) fails the successful-sample and
failing-sample cases;
``M133-quality-before-gap`` (let a quality warning degrade a candidate that
has no caller samples) fails the no-sample quality and selection cases.

ADMIT (treesitter-chunker#362) admits a local grammar only under its approved
pin, so the managers here pin the artifact they validate. One pin per language
cannot admit two different artifacts, so in the selection case the PACKAGE
build is a RECORD-verified file of a stand-in for our own wheel (admitted
without a pin, decision M3) while the padded USER build holds the pin.
"""

from __future__ import annotations

import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityLevel,
    CompatibilityResult,
    SmartSelector,
)
from chunker.grammar_management.core import (
    GrammarManager,
    ValidationLevel,
    load_compiled_grammar,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packages/baml-grammar/tests/fixtures/declarations.baml"
GRAMMAR_SRC = ROOT / "packages/baml-grammar/src"
GAP_WARNING = "No test samples available for baml"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="The checked-in BAML grammar builds as a Linux shared library",
)


def _pins(library: Path) -> dict[str, dict[str, str]]:
    return {"baml": {"sha256": sha256(library.read_bytes()).hexdigest()}}


def _record_verified_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, library_bytes: bytes
) -> Path:
    """Our wheel's grammar directory holding a RECORD-verified ``libbaml.so``."""
    import base64
    from importlib.metadata import PathDistribution

    from chunker._internal import package_supplier

    site = tmp_path / "site"
    package = site / "chunker"
    build = package / "data" / "grammars" / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (build / "libbaml.so").write_bytes(library_bytes)
    dist_info = site / "treesitter_chunker-6.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: treesitter-chunker\nVersion: 6.0.0\n",
        encoding="utf-8",
    )
    encoded = base64.urlsafe_b64encode(sha256(library_bytes).digest()).rstrip(b"=")
    (dist_info / "RECORD").write_text(
        "chunker/__init__.py,,\n"
        f"chunker/data/grammars/build/libbaml.so,sha256={encoded.decode()},"
        f"{len(library_bytes)}\n",
        encoding="utf-8",
    )
    distribution = PathDistribution(dist_info)
    monkeypatch.setattr(package_supplier, "_package_distribution", lambda: distribution)
    monkeypatch.setattr(
        package_supplier, "_package_init_file", lambda: package / "__init__.py"
    )
    package_supplier._package_grammar_records.cache_clear()
    return build


def _build(library: Path) -> None:
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(GRAMMAR_SRC),
            str(GRAMMAR_SRC / "parser.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def baml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A real compiled BAML grammar in an isolated grammar manager."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    user_dir = tmp_path / "user"
    package_dir = tmp_path / "package"
    user_dir.mkdir()
    package_dir.mkdir()
    library = package_dir / "libbaml.so"
    _build(library)
    source = FIXTURE.read_text(encoding="utf-8")
    tree = load_compiled_grammar(library, "baml").parse(source.encode("utf-8"))
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error
    manager = GrammarManager(
        user_dir=user_dir,
        package_dir=package_dir,
        cache_dir=tmp_path / "cache",
        trusted_artifacts=_pins(library),
    )
    return manager, library, source


def test_real_validator_reports_the_recognized_evidence_gap(baml) -> None:
    manager, library, _source = baml
    validation = manager._validator.validate_grammar(
        library, "baml", ValidationLevel.STANDARD
    )
    assert validation.is_valid, validation.errors
    assert validation.warnings == [GAP_WARNING]
    assert "samples_tested" not in validation.performance_metrics


def test_successful_caller_sample_is_compatible_evidence(baml) -> None:
    manager, library, source = baml
    result = CompatibilityChecker(manager).check_compatibility(
        "baml", code_samples=[source], grammar_path=library
    )
    assert result.test_results is not None
    assert result.test_results["successful_samples"] == 1
    assert result.test_results["success_rate"] == 1.0
    assert result.level == CompatibilityLevel.COMPATIBLE
    assert result.score == pytest.approx(1.0)
    assert result.issues == []
    # The gap is still reported; it just is not a degradation.
    assert result.warnings == [GAP_WARNING]


def test_failing_caller_samples_still_count_against(baml) -> None:
    manager, library, source = baml
    broken = source + "\nclass Broken {\n"
    parser = load_compiled_grammar(library, "baml")
    assert parser.parse(broken.encode("utf-8")).root_node.has_error
    result = CompatibilityChecker(manager).check_compatibility(
        "baml", code_samples=[source, broken, broken], grammar_path=library
    )
    assert result.test_results["successful_samples"] == 1
    assert result.level == CompatibilityLevel.INCOMPATIBLE
    assert result.score == pytest.approx(1 / 3)


def test_no_sample_evidence_is_unknown_not_degraded(baml) -> None:
    manager, library, _source = baml
    result = CompatibilityChecker(manager).check_compatibility(
        "baml", grammar_path=library
    )
    assert result.test_results is None
    assert result.level == CompatibilityLevel.UNKNOWN
    assert result.score == pytest.approx(0.3)
    assert result.warnings == [GAP_WARNING]
    assert result.issues == []


def test_quality_warning_beside_the_gap_still_degrades(baml) -> None:
    manager, library, source = baml
    checker = CompatibilityChecker(manager)
    result = checker._perform_detailed_compatibility_check(
        CompatibilityResult("baml", "local", None, CompatibilityLevel.UNKNOWN),
        {
            "path": str(library),
            "validation": {
                "errors": [],
                "warnings": [GAP_WARNING, "Parsing performance is slow"],
            },
        },
        [source],
        library,
    )
    assert result.test_results["successful_samples"] == 1
    assert result.level == CompatibilityLevel.DEGRADED
    assert result.score == pytest.approx(0.7)
    assert result.warnings == [GAP_WARNING, "Parsing performance is slow"]


def test_no_samples_stays_unknown_beside_a_quality_warning(baml) -> None:
    """With nothing parsed, a quality warning must not outrank a bare gap."""
    manager, library, _source = baml
    result = CompatibilityChecker(manager)._perform_detailed_compatibility_check(
        CompatibilityResult("baml", "local", None, CompatibilityLevel.UNKNOWN),
        {
            "path": str(library),
            "validation": {
                "errors": [],
                "warnings": [GAP_WARNING, "Grammar file is unusually large"],
            },
        },
        [],
        library,
    )
    assert result.test_results is None
    assert result.level == CompatibilityLevel.UNKNOWN
    assert result.score == pytest.approx(0.3)
    assert result.warnings == [GAP_WARNING, "Grammar file is unusually large"]


def test_selection_does_not_prefer_a_warned_artifact_without_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claude's round-1 repro: a USER build padded past 50 MB vs a clean PACKAGE."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from chunker._internal import package_supplier

    user_dir = tmp_path / "user"
    user_dir.mkdir()
    user_library = user_dir / "libbaml.so"
    _build(user_library)
    clean_build = tmp_path / "clean-libbaml.so"
    _build(clean_build)
    # The clean PACKAGE build is a RECORD-verified file of our own wheel (no pin
    # needed); the padded USER build holds the language's one pin.
    package_dir = _record_verified_package(
        tmp_path, monkeypatch, clean_build.read_bytes()
    )
    package_library = package_dir / "libbaml.so"
    with user_library.open("r+b") as handle:  # sparse padding past 50 MB
        handle.truncate(51 * 1024 * 1024)
    source = FIXTURE.read_bytes()
    for library in (user_library, package_library):
        tree = load_compiled_grammar(library, "baml").parse(source)
        assert not tree.root_node.has_error
    try:
        manager = GrammarManager(
            user_dir=user_dir,
            package_dir=package_dir,
            cache_dir=tmp_path / "cache",
            trusted_artifacts=_pins(user_library),
        )
        checker = CompatibilityChecker(manager)
        warned = checker.check_compatibility("baml", grammar_path=user_library)
        clean = checker.check_compatibility("baml", grammar_path=package_library)
        # Basic validation reports the size before the standard gap.
        assert warned.warnings == ["Grammar file is unusually large", GAP_WARNING]
        assert warned.level == clean.level == CompatibilityLevel.UNKNOWN
        assert clean.warnings == [GAP_WARNING]

        selected = SmartSelector(manager, checker).select_best_grammar("baml")
        assert selected is not None
        assert selected.grammar_path == package_library
    finally:
        package_supplier._package_grammar_records.cache_clear()
