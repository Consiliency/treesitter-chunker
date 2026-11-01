"""Caller samples count as compatibility evidence (treesitter-chunker#133).

A grammar without built-in validation samples gets the validator warning
``No test samples available for <language>``. That warning is an evidence
gap, not a performance finding: it must not classify a candidate as
``DEGRADED`` by itself. Caller-supplied samples parsed with the real artifact
are the evidence. Named mutation ``M133-gap-degrades`` (treat the gap as a
quality warning, the old behavior) fails the successful-sample and no-sample
cases.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from chunker.grammar_management.compatibility import (
    CompatibilityChecker,
    CompatibilityLevel,
    CompatibilityResult,
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
    source = FIXTURE.read_text(encoding="utf-8")
    tree = load_compiled_grammar(library, "baml").parse(source.encode("utf-8"))
    assert tree.root_node.type == "source_file"
    assert not tree.root_node.has_error
    manager = GrammarManager(
        user_dir=user_dir, package_dir=package_dir, cache_dir=tmp_path / "cache"
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
